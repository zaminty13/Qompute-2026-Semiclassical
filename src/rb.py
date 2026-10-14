import random
from pulses import IDENTITY, SEQUENCE_NAMES, sequence_unitary, sequence_duration_ns, sequence_segments
from scipy.stats import binom
import numpy as np
from decoherence import sequence_superop
from qiskit.quantum_info import SuperOp
from qiskit.quantum_info import DensityMatrix

X_CHOICES = (True, False)
X_PROBABILITY = X_CHOICES.count(True) / len(X_CHOICES)


def _integer(value, name, minimum=0):
  if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)) or value < minimum:
    raise ValueError(f'{name} must be an integer >= {minimum}.')
  return int(value)


def random_sequence(length, *, rng=None):
  length = _integer(length, 'length')
  generator = random if rng is None else rng
  return [generator.choice(X_CHOICES) for _ in range(length)]

def needs_inverting_gate(sequence):
  count = sum(sequence)
  return count % 2 == 1

def sequence_to_unitary(flips, pulse_type, omega_rad_per_ns, amplitude_error=0.0,
                        detuning_rad_per_ns=0.0):
  x_gate_matrix=sequence_unitary(pulse_type, omega_rad_per_ns, amplitude_error,
                                 detuning_rad_per_ns)
  total=IDENTITY.copy()
  for f in flips:
    if f:
      total=x_gate_matrix @ total
  if needs_inverting_gate(flips):
    total=x_gate_matrix @ total
  return total

def survival_probability(total_unitary):
  initial_state=np.array([1,0])
  final_state=total_unitary @ initial_state
  probability_zero=abs(final_state[0]) ** 2
  return probability_zero


def average_survival_probability(length, num_trials, pulse_type, omega_rad_per_ns,
                                 amplitude_error=0.0, detuning_rad_per_ns=0.0):
  _integer(num_trials, 'num_trials', 1)
  _integer(length, 'length')
  probabilities = []
  for _ in range(num_trials):
    flips = random_sequence(length)
    total=sequence_to_unitary(flips, pulse_type, omega_rad_per_ns,
                              amplitude_error, detuning_rad_per_ns)
    probabilities.append(survival_probability(total))

  return sum(probabilities)/len(probabilities)


def rb_decay_curve(lengths, num_trials, pulse_type, omega_rad_per_ns,
                   amplitude_error=0.0, detuning_rad_per_ns=0.0):
  results = []
  for length in lengths:
    avg_prob = average_survival_probability(length, num_trials, pulse_type, omega_rad_per_ns,
                                            amplitude_error, detuning_rad_per_ns)
    results.append((length, avg_prob))
  return results


def sequence_to_superop(flips, pulse_type, omega_rad_per_ns, amplitude_error=0.0,
                        detuning_rad_per_ns=0.0, t1_ns=np.inf, t2_ns=np.inf):
  x_gate_superop = sequence_superop(pulse_type, omega_rad_per_ns, amplitude_error,
                                    detuning_rad_per_ns, t1_ns=t1_ns, t2_ns=t2_ns)
  total=np.eye(4, dtype=complex)
  for f in flips:
    if f:
      total = x_gate_superop.data @ total
  if needs_inverting_gate(flips):
    total = x_gate_superop.data @ total
  return SuperOp(total)

def survival_probability_from_superop(total_superop):
  rho0=DensityMatrix([[1,0],[0,0]]) #this is |0><0|
  rho_final = rho0.evolve(total_superop)
  probability_zero = np.real(rho_final.data[0,0])
  return probability_zero

def average_survival_probability_with_decoherence(length, num_trials, pulse_type, omega_rad_per_ns,
                                                  amplitude_error=0.0, detuning_rad_per_ns=0.0,
                                                  t1_ns=np.inf, t2_ns=np.inf):
  _integer(num_trials, 'num_trials', 1)
  _integer(length, 'length')
  probabilities = []
  for _ in range(num_trials):
    flips = random_sequence(length)
    total = sequence_to_superop(flips, pulse_type, omega_rad_per_ns,
                                amplitude_error, detuning_rad_per_ns, t1_ns,
                                t2_ns)
    probabilities.append(survival_probability_from_superop(total))
  return sum(probabilities) / len(probabilities)

def rb_decay_curve_with_decoherence(lengths, num_trials, pulse_type, omega_rad_per_ns,
                                    amplitude_error=0.0, detuning_rad_per_ns=0.0, t1_ns=np.inf,
                                    t2_ns=np.inf):
  results = []
  for length in lengths:
    avg_prob = average_survival_probability_with_decoherence(length, num_trials, pulse_type,
                                                             omega_rad_per_ns, amplitude_error,
                                                             detuning_rad_per_ns, t1_ns, t2_ns)
    results.append((length, avg_prob))
  return results


def sample_sequences(lengths, num_trials, seed):
  lengths = tuple(_integer(m, 'length') for m in lengths)
  if not lengths or len(set(lengths)) != len(lengths):
    raise ValueError('lengths must be nonempty and unique.')
  num_trials = _integer(num_trials, 'num_trials', 2)
  seed = _integer(seed, 'seed')
  rng = random.Random(seed)
  return {m: [tuple(random_sequence(m, rng=rng)) for _ in range(num_trials)] for m in lengths}


def sequence_cost(flips, pulse_type, omega_rad_per_ns):
  flips = tuple(flips)
  if any(not isinstance(f, (bool, np.bool_)) for f in flips):
    raise ValueError('Sequence entries must be Boolean X/identity choices.')
  k = sum(flips)
  recovery = k % 2
  count = k + recovery
  duration = sequence_duration_ns(pulse_type, omega_rad_per_ns)
  return {'sampled_x_count': int(k), 'recovery_x_count': int(recovery),
          'executed_x_count': int(count),
          'physical_segment_count': int(count * len(sequence_segments(pulse_type))),
          'duration_ns': float(count * duration)}


def count_survival(channel, count, initial_state=0):
  count = _integer(count, 'count')
  if initial_state not in (0, 1):
    raise ValueError('initial_state must be 0 or 1.')
  index = 3 * initial_state
  value = float(np.real(np.linalg.matrix_power(np.asarray(channel), count)[index, index]))
  if not np.isfinite(value) or value < -1e-10 or value > 1 + 1e-10:
    raise ValueError('Unphysical survival probability.')
  return float(np.clip(value, 0., 1.))


def exact_survival(channel, length, initial_state=0, q=X_PROBABILITY):
  length = _integer(length, 'length')
  if not np.isfinite(q) or not 0 <= q <= 1:
    raise ValueError('q must be a finite probability.')
  k = np.arange(length + 1)
  counts = k + k % 2
  weights = binom.pmf(k, length, q)
  values = np.array([count_survival(channel, int(n), initial_state) for n in counts])
  mean = float(weights @ values)
  return {'exact_mean_survival': mean,
          'exact_sequence_variance': float(weights @ (values - mean)**2),
          'exact_mean_executed_x': float(weights @ counts)}


def run_survival_study(*, lengths=(2, 4, 8, 16, 32), num_trials=512, seed=2026,
                       amplitude_error=.05, detuning_rad_per_ns=.003,
                       primitive_duration_ns=100., t1_ns=30000., t2_ns=20000.,
                       initial_state=0):
  if not np.isfinite(primitive_duration_ns) or primitive_duration_ns <= 0:
    raise ValueError('primitive_duration_ns must be positive and finite.')
  draws = sample_sequences(lengths, num_trials, seed)
  omega = np.pi / primitive_duration_ns
  summary, samples = [], []
  for name in SEQUENCE_NAMES:
    channel = sequence_superop(name, omega, amplitude_error, detuning_rad_per_ns,
                               t1_ns=t1_ns, t2_ns=t2_ns).data
    duration = float(sequence_duration_ns(name, omega))
    for length, sequences in draws.items():
      values = []
      costs = []
      for trial, flips in enumerate(sequences):
        cost = sequence_cost(flips, name, omega)
        survival = count_survival(channel, cost['executed_x_count'], initial_state)
        values.append(survival)
        costs.append(cost)
        samples.append({'pulse_type': name, 'length': length, 'trial': trial,
                        'initial_state': initial_state,
                        'sequence': ''.join('X' if f else 'I' for f in flips),
                        **cost, 'survival_probability': survival})
      exact = exact_survival(channel, length, initial_state)
      times = np.array([c['duration_ns'] for c in costs])
      summary.append({'pulse_type': name, 'length': length, 'initial_state': initial_state,
                      'num_trials': num_trials, 'x_duration_ns': duration,
                      'mean_survival': float(np.mean(values)),
                      'sequence_standard_error': float(np.std(values, ddof=1) / np.sqrt(num_trials)),
                      **exact,
                      'exact_standard_error': float(np.sqrt(exact['exact_sequence_variance'] / num_trials)),
                      'mean_executed_x': float(np.mean([c['executed_x_count'] for c in costs])),
                      'mean_physical_segments': float(np.mean([c['physical_segment_count'] for c in costs])),
                      'mean_duration_ns': float(np.mean(times)),
                      'exact_mean_duration_ns': exact['exact_mean_executed_x'] * duration,
                      'min_duration_ns': float(min(times)), 'max_duration_ns': float(max(times))})
  return {'config': {'seed': seed, 'lengths': list(draws), 'num_trials': num_trials,
                    'amplitude_error': amplitude_error, 'detuning_rad_per_ns': detuning_rad_per_ns,
                    'primitive_duration_ns': primitive_duration_ns, 'omega_rad_per_ns': float(omega),
                    't1_ns': float(t1_ns) if np.isfinite(t1_ns) else 'infinity',
                    't2_ns': float(t2_ns) if np.isfinite(t2_ns) else 'infinity',
                    'initial_state': initial_state, 'x_probability': X_PROBABILITY,
                    'identity_duration_ns': 0., 'identity_noise': 'none',
                    'recovery': 'noisy X if ideal sampled X parity is odd',
                    'control_errors': 'fixed across all operations and trials',
                    'uncertainty': 'one standard error across sampled sequences; no shot noise'},
          'summary': summary, 'samples': samples}
