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
  
  ax.set_xlabel('Sequence length (number of gates)')
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

  ax.set(xlabel='Sequence length (number of gates)',
         ylabel='Survival probability (to |0>)',
         ylim=(0, 1.02),
         title=f'Randomized benchmarking decay{title_suffix}')
  ax.legend()
  _style(ax)
  return fig

def main():
  lengths = [2,4,8,16,32]
  num_trials = 100
  omega_rad_per_ns = np.pi/100
  amplitude_error = 0.05
  detuning_rad_per_ns = 0.003
  t1_ns = 30000
  t2_ns = 20000
  pulse_types = ["primitive", "BB1", "CORPSE"]
  
  all_results={}
  all_results_decoherence = {}
  summary_rows = []
  
  for pulse_type in pulse_types:
    decay_curve_data = rb_decay_curve(lengths, num_trials, pulse_type,
                                      omega_rad_per_ns, amplitude_error,
                                      detuning_rad_per_ns)
    A, p, B, r = fit_decay(decay_curve_data)
    all_results[pulse_type]= (decay_curve_data, A, p, B)
    summary_rows.append({'pulse_type': pulse_type, 'model': 'coherent', 'A': A, 'p': p, 'B': B,
                        'error_per_gate': r})
  for pulse_type in pulse_types:
    decay_curve_data = rb_decay_curve_with_decoherence(lengths, num_trials,
                                                       pulse_type, omega_rad_per_ns, amplitude_error,
                                                       detuning_rad_per_ns, t1_ns, t2_ns)
    A, p, B, r = fit_decay(decay_curve_data)
    all_results_decoherence[pulse_type] = (decay_curve_data, A, p, B)
    summary_rows.append({'pulse_type': pulse_type, 'model': 'with_decoherence', 'A': A,
                         'p': p, 'B': B, 'error_per_gate': r})
    
  output_dir = Path(__file__).resolve().parents[1] / 'results' / 'rb'
  output_dir.mkdir(parents=True, exist_ok=True)
  
  with open(output_dir / 'rb_summary.csv', 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['pulse_type', 'model', 'A', 'p', 'B', 'error_per_gate'])
    writer.writeheader()
    writer.writerows(summary_rows)

  params_text = (f'\nOmega = {omega_rad_per_ns:.6g} rad/ns; amplitude error = {amplitude_error:.0%}; '
                 f'detuning = {detuning_rad_per_ns:.4g} rad/ns')

  fig_coherent = plot_all_sequences(all_results, pulse_types,
      title_suffix=params_text + '\nCoherent errors only (no decoherence)')
  fig_coherent.savefig(output_dir / 'rb_comparison_coherent.png', dpi=180)

  fig_decoherence = plot_all_sequences(all_results_decoherence, pulse_types,
      title_suffix=params_text + f'\nWith T1 = {t1_ns:g} ns, T2 = {t2_ns:g} ns decoherence')
  fig_decoherence.savefig(output_dir / 'rb_comparison_decoherence.png', dpi=180)
  
  for row in summary_rows:
    print(f"{row['pulse_type']:10s} {row['model']:17s} error per gate = {row['error_per_gate']:.6f}")
    
if __name__ == '__main__':
  main()