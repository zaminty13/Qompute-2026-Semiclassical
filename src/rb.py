import random
from pulses import IDENTITY, sequence_unitary
import numpy as np
from decoherence import sequence_superop
from qiskit.quantum_info import SuperOp
from qiskit.quantum_info import DensityMatrix

def random_sequence(length):
  return[random.choice([True,False]) for _ in range(length)]

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