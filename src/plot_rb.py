from scipy.optimize import curve_fit
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import csv
from rb import rb_decay_curve, rb_decay_curve_with_decoherence

COLORS = ('#2166ac', '#b35806', '#1b7837')
LINESTYLES = ('-', '-', '--')


def _style(ax):
  ax.grid(alpha=.25)
  ax.spines[['top', 'right']].set_visible(False)


def exponential_decay(m, A, p, B):
  return A * p**m + B

def fit_decay(decay_curve_data):
  lengths = np.array([pair[0] for pair in decay_curve_data])
  probabilities = np.array([pair[1] for pair in decay_curve_data])

  initial_guess = [0.5, 0.99, 0.5]
  (A, p, B), _ = curve_fit(exponential_decay, lengths, probabilities, p0=initial_guess,
                           bounds=([0,0,0], [1,1,1]))
  r = (1 - p) /2
  return A, p, B, r

def plot_decay_curve(decay_curve_data, A, p, B, pulse_type):
  lengths = [pair[0] for pair in decay_curve_data]
  probabilities = [pair[1] for pair in decay_curve_data]
  fig, ax = plt.subplots()
  ax.scatter(lengths, probabilities, label=f'{pulse_type} data')

  smooth_lengths = np.linspace(min(lengths), max(lengths), 200)
  fitted_probabilities = exponential_decay(smooth_lengths, A, p, B)
  ax.plot(smooth_lengths, fitted_probabilities, label=f'{pulse_type} fit')

  ax.set_xlabel('Sampled X/identity slots (recovery excluded)')
  ax.set_ylabel('Survival probability')
  ax.legend()
  return fig

def plot_all_sequences(all_results, pulse_types, title_suffix=''):
  fig, ax = plt.subplots(figsize=(9, 5.5), layout='constrained')

  for pulse_type, color, style in zip(pulse_types, COLORS, LINESTYLES):
    decay_curve_data, A, p, B = all_results[pulse_type]
    lengths = [pair[0] for pair in decay_curve_data]
    probabilities = [pair[1] for pair in decay_curve_data]
    ax.scatter(lengths, probabilities, color=color, label=f'{pulse_type} data')
    smooth_lengths = np.linspace(min(lengths), max(lengths), 200)
    fitted_probabilities = exponential_decay(smooth_lengths, A, p, B)
    ax.plot(smooth_lengths, fitted_probabilities, color=color, linestyle=style,
            linewidth=2, label=f'{pulse_type} fit')

  ax.set(xlabel='Sampled X/identity slots (recovery excluded)',
         ylabel='Survival probability (to |0>)',
         ylim=(0, 1.02),
         title=f'Historical X/identity descriptive fit (not Clifford RB){title_suffix}')
  ax.legend()
  _style(ax)
  return fig

def write_rows(path, rows):
  with path.open('x', newline='', encoding='utf-8') as stream:
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)


def _file_sha256(path):
  import hashlib
  data = Path(path).read_bytes()
  if Path(path).suffix in ('.py', '.csv'):
    data = data.replace(b'\r\n', b'\n')
  return hashlib.sha256(data).hexdigest()


def build_study(output, *, seed=2026, num_trials=512):
  import importlib.metadata
  import json
  from rb import run_survival_study
  from compare_rb_selector import compare_study
  output = Path(output)
  output.mkdir(parents=True, exist_ok=False)
  cases = {'mixed_coherent': dict(t1_ns=np.inf, t2_ns=np.inf),
           'mixed_decoherence': {},
           'amplitude_decoherence': dict(detuning_rad_per_ns=0.),
           'mixed_decoherence_state1': dict(initial_state=1)}
  studies = {case: run_survival_study(seed=seed, num_trials=num_trials, **conditions)
             for case, conditions in cases.items()}
  summaries = [{'case': case, **row} for case, study in studies.items() for row in study['summary']]
  samples = [{'case': case, **row} for case, study in studies.items() for row in study['samples']]
  comparisons = [{'case': case, **row} for case, study in studies.items()
                 if study['config']['initial_state'] == 0 for row in compare_study(study)]
  write_rows(output/'summary.csv', summaries)
  write_rows(output/'samples.csv', samples)
  write_rows(output/'selector_comparison.csv', comparisons)
  names = ('primitive', 'BB1', 'CORPSE')
  fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
  for ax, case, title in zip(axs, ('mixed_coherent', 'mixed_decoherence'),
                             ('Coherent only', 'T1/T2 = 30/20 us')):
    for name, color in zip(names, COLORS):
      rows = [r for r in studies[case]['summary'] if r['pulse_type'] == name]
      ax.errorbar([r['length'] for r in rows], [r['mean_survival'] for r in rows],
                  yerr=[r['sequence_standard_error'] for r in rows], fmt='o', capsize=3,
                  color=color, label=name)
      ax.plot([r['length'] for r in rows], [r['exact_mean_survival'] for r in rows],
              color=color, linewidth=1.5)
    ax.set(xlabel='Sampled X/identity slots m (recovery excluded)', ylabel='Return probability to |0>',
           title=title, ylim=(0, 1.02))
    ax.legend(); _style(ax)
  fig.suptitle('Simulated X/identity survival: 5% amplitude error, detuning 0.003 rad/ns\n'
               'Points: sampled mean +/- 1 sequence SE; lines: exact binomial means')
  fig.savefig(output/'survival_by_length.png', dpi=180)
  plt.close(fig)
  fig, ax = plt.subplots(figsize=(9, 5), layout='constrained')
  for name, color in zip(names, COLORS):
    rows = [r for r in studies['mixed_decoherence']['summary'] if r['pulse_type'] == name]
    ax.errorbar([r['mean_duration_ns']/1000 for r in rows], [r['mean_survival'] for r in rows],
                yerr=[r['sequence_standard_error'] for r in rows], fmt='o-', color=color,
                capsize=3, label=name)
  ax.set(xlabel='Sampled ensemble MEAN control duration (us)', ylabel='Mean return probability to |0>',
         title='Simulated mixed-error survival, T1/T2 = 30/20 us\n'
               'Individual durations vary; pulse families are NOT matched in time', ylim=(0, 1.02))
  ax.legend(); _style(ax)
  fig.savefig(output/'survival_by_mean_duration.png', dpi=180)
  plt.close(fig)
  fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
  rows = [r for r in comparisons if r['case'] == 'amplitude_decoherence' and r['length'] == 32]
  for ax, field, label in zip(axs, ('direct_fidelity', 'mean_survival'),
                            ('Single-gate average fidelity', 'Mean return to |0>, m = 32')):
    values = [r[field] for r in rows]
    errors = [r['sequence_standard_error'] if field == 'mean_survival' else 0. for r in rows]
    ax.bar(names, values, color=COLORS, yerr=errors, capsize=4)
    ax.set(ylabel=label, ylim=(0, 1.04)); _style(ax)
    for i, value in enumerate(values):
      ax.text(i, value+.018, f'{value:.4f}', ha='center')
  axs[0].axhline(.99, linestyle='--', color='black', label='Selector threshold 0.99')
  axs[0].legend(loc='lower left')
  fig.suptitle('Simulation: amplitude +5%, detuning 0, T1/T2 = 30/20 us\n'
               'Selector chooses primitive (shortest qualifying); survival is a different observable')
  fig.savefig(output/'selector_vs_survival.png', dpi=180)
  plt.close(fig)
  root = Path(__file__).resolve().parents[1]
  sources = ['src/rb.py', 'src/plot_rb.py', 'src/compare_rb_selector.py', 'src/pulses.py',
             'src/decoherence.py', 'src/select_pulse.py']
  metadata = {'protocol': 'randomized X/identity state-return study; not Clifford RB',
              'teammate_source_commit': '7e31e441174e3e0c44bfcd2776bfd765d6607eed',
              'integration_base': 'd6982225f9f08a69f825c2d44c96bf38c0daeac3',
              'cases': {case: study['config'] for case, study in studies.items()},
              'checksum_convention': 'SHA-256; Python and CSV CRLF normalized to LF; other files hashed as bytes',
              'source_sha256': {name: _file_sha256(root/name) for name in sources},
              'versions': {name: importlib.metadata.version(name) for name in ('numpy', 'scipy', 'qiskit', 'matplotlib')},
              'files_sha256': {p.name: _file_sha256(p) for p in sorted(output.iterdir())},
              'legacy_fit_status': 'superseded; no validated RB error interpretation',
              'sampling': 'same locally seeded sequences for all pulse families and cases; no measurement shots'}
  (output/'metadata.json').write_text(json.dumps(metadata, indent=2, allow_nan=False)+'\n', encoding='utf-8')
  return studies


def main():
  import argparse
  parser = argparse.ArgumentParser(description='Reproducible X/identity survival simulations, not Clifford RB')
  parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1]/'results/rb/survival_study')
  parser.add_argument('--seed', type=int, default=2026)
  parser.add_argument('--trials', type=int, default=512)
  args = parser.parse_args()
  build_study(args.output, seed=args.seed, num_trials=args.trials)
  print('Saved survival study:', args.output)


if __name__ == '__main__':
  main()
