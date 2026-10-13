"""Generate reproducible PulseWise competition figures from team pulse models.

Run from the repository root:
    python src/plot_selector.py --quick
    python src/plot_selector.py

Outputs are written to results/selector/; no other team files are modified.
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from pulses import SEQUENCE_NAMES
from select_pulse import evaluate_pulses, select_pulse, robust_select_pulse

OUT = Path(__file__).resolve().parents[1] / 'results' / 'selector'
COLORS = {'primitive': '#3269AB', 'BB1': '#128A73', 'CORPSE': '#9B5CC4'}
NONE = '#DDE3EA'


def save_csv(filename, rows):
    if not rows:
        return
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / filename).open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def savefig(fig, filename):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / filename, dpi=240, bbox_inches='tight', facecolor='white')
    plt.close(fig)


def plot_tradeoff(samples=37, threshold=.997):
    candidates = []
    for primitive_duration in np.linspace(50, 250, samples):
        candidates.extend(evaluate_pulses(
            amplitude_error=.05, detuning_rad_per_ns=0,
            primitive_duration_ns=float(primitive_duration),
            t1_ns=200000, t2_ns=150000))
    save_csv('fidelity_duration.csv', candidates)
    feasible = [r for r in candidates if r['fidelity'] >= threshold - 1e-12]
    winner = min(feasible, key=lambda r: (r['duration_ns'], -r['fidelity'])) if feasible else None
    frontier = []
    highest_so_far = -np.inf
    for row in sorted(candidates, key=lambda r: (r['duration_ns'], -r['fidelity'])):
        if row['fidelity'] > highest_so_far + 1e-11:
            frontier.append(row)
            highest_so_far = row['fidelity']
    fig, ax = plt.subplots(figsize=(9.5, 5.9), layout='constrained')
    for name in SEQUENCE_NAMES:
        rows = sorted((r for r in candidates if r['sequence'] == name),
                      key=lambda r: r['duration_ns'])
        ax.plot([r['duration_ns'] for r in rows],
                [100*r['fidelity'] for r in rows],
                linewidth=2.3, label=name, color=COLORS[name])
    ax.plot([r['duration_ns'] for r in frontier],
            [100*r['fidelity'] for r in frontier], color='#27323D',
            ls='--', linewidth=1.5, label='Sampled Pareto frontier')
    ax.axhline(100*threshold, color='#CB643A', ls=':', lw=2,
               label=f'Threshold {threshold:.1%}')
    if winner:
        ax.scatter(winner['duration_ns'], 100*winner['fidelity'], s=270,
                   marker='*', c='#EDBC4C', edgecolors='#121820', linewidths=1,
                   zorder=5, label='Fastest qualifying candidate')
    ax.set(xlabel='Actual total pulse duration (ns)',
           ylabel='Average gate fidelity (%)',
           title='When is the longer, error-resistant pulse worth it?')
    ax.text(.02, .02, 'Fixed 5% amplitude error, zero detuning; T1=200 μs, T2=150 μs\n'
            'Shared drive within each comparison; variable drive across duration sweep',
            transform=ax.transAxes, fontsize=8, va='bottom', color='#555F67')
    ax.grid(alpha=.18)
    ax.legend(loc='lower right', fontsize=8, ncol=2)
    savefig(fig, 'fidelity_duration.png')
    return winner


def plot_map(points=35, threshold=.997):
    primitive_duration, t1, t2 = 100., 200000., 150000.
    amp_grid = np.linspace(-.12, .12, points)
    det_grid = np.linspace(-.20, .20, points)
    omega = np.pi / primitive_duration
    mapping = {'none': 0, 'primitive': 1, 'BB1': 2, 'CORPSE': 3}
    z = np.zeros((points, points), dtype=int)
    rows = []
    for i, det in enumerate(det_grid):
        for j, amp in enumerate(amp_grid):
            winner, _ = select_pulse(
                min_fidelity=threshold, amplitude_error=float(amp),
                detuning_rad_per_ns=float(det*omega),
                primitive_duration_ns=primitive_duration, t1_ns=t1, t2_ns=t2)
            name = winner['sequence'] if winner else 'none'
            z[i,j] = mapping[name]
            rows.append({'amplitude_error': float(amp),
                         'detuning_over_omega': float(det),
                         'selected_pulse': name})
    save_csv('pulse_selection_map.csv', rows)
    colors = [NONE, COLORS['primitive'], COLORS['BB1'], COLORS['CORPSE']]
    fig, ax = plt.subplots(figsize=(9.2, 6.3), layout='constrained')
    ax.imshow(z, origin='lower', interpolation='nearest', aspect='auto',
              extent=(100*amp_grid[0], 100*amp_grid[-1], det_grid[0], det_grid[-1]),
              cmap=ListedColormap(colors), vmin=-.5, vmax=3.5)
    ax.set(xlabel='Amplitude calibration error (%)',
           ylabel=r'Normalized detuning $\Delta/\Omega$',
           title=f'Which pulse qualifies fastest?  |  {threshold:.1%} fidelity threshold')
    ax.text(.02, .02, 'Primitive X=100 ns; T1=200 μs, T2=150 μs',
            transform=ax.transAxes, color='#202833', fontsize=8,
            bbox=dict(facecolor='white', alpha=.85, edgecolor='none', pad=4))
    legend = [Patch(facecolor=colors[i], label=label) for i,label in enumerate(
        ('No feasible pulse', 'Primitive X', 'BB1', 'CORPSE'))]
    ax.legend(handles=legend, fontsize=8, loc='upper right', framealpha=.96)
    savefig(fig, 'pulse_selection_map.png')
    return {name: int(np.sum(z == code)) for name, code in mapping.items()}


def plot_robust(threshold=.997, points=5):
    winner, rows = robust_select_pulse(min_fidelity=threshold, points_per_axis=points)
    save_csv('gridium_inspired_robustness.csv', rows)
    fig, ax = plt.subplots(figsize=(9, 5.5), layout='constrained')
    for i,row in enumerate(rows):
        nominal, worst = 100*row['nominal_fidelity'], 100*row['sampled_worst_fidelity']
        ax.plot([i,i], [worst,nominal], lw=4, color='#A1ABB4', zorder=1)
        ax.scatter(i, nominal, marker='o', s=125, c=COLORS[row['sequence']],
                   edgecolors='white', linewidths=1, zorder=3)
        ax.scatter(i, worst, marker='D', s=140, c=COLORS[row['sequence']],
                   edgecolors='#1B2229', linewidths=1, zorder=4)
        ax.annotate('PASS' if row['robust_pass'] else 'FAIL',
                    (i,worst), xytext=(0,-19), textcoords='offset points',
                    ha='center', fontsize=9, fontweight='bold')
    ax.axhline(100*threshold, c='#C9623A', ls='--', lw=1.8)
    ax.set_xticks(range(len(rows)),
                  [f"{r['sequence']}\n{r['duration_ns']:.0f} ns" for r in rows])
    ax.set_ylim(min(100*r['sampled_worst_fidelity'] for r in rows)-.6, 100.1)
    ax.set(ylabel='Average gate fidelity (%)',
           title='Nominal accuracy is not the same as robust accuracy')
    ax.text(.02, .03, '5% amplitude ±2 percentage points; normalized detuning ±0.02\n'
            'Finite-grid worst case only (not a continuous guarantee)',
            transform=ax.transAxes, fontsize=8, va='bottom', color='#47515B')
    ax.grid(axis='y', alpha=.18)
    ax.legend(handles=[Line2D([],[],marker='o',color='none',markerfacecolor='gray',
                             label='Nominal fidelity'),
                       Line2D([],[],marker='D',color='none',markerfacecolor='gray',
                             label='Worst sampled fidelity'),
                       Line2D([],[],color='#C9623A',ls='--',label=f'Threshold {threshold:.1%}')],
              fontsize=8, loc='lower right')
    savefig(fig, 'gridium_inspired_robustness.png')
    return winner


def plot_coherence_crossover(samples=29):
    t1_grid = np.geomspace(5000, 500000, samples)
    rows = []
    for t1 in t1_grid:
        rows.extend(evaluate_pulses(amplitude_error=.05, detuning_rad_per_ns=0.,
                                    primitive_duration_ns=100.,
                                    t1_ns=float(t1), t2_ns=float(2*t1/3)))
    save_csv('coherence_crossover.csv', rows)
    fig, ax = plt.subplots(figsize=(9,5.5), layout='constrained')
    for s in SEQUENCE_NAMES:
        subset = [r for r in rows if r['sequence'] == s]
        ax.plot([r['t1_ns']/1000 for r in subset],
                [100*r['fidelity'] for r in subset], color=COLORS[s],
                label=s, linewidth=2.5)
    ax.axvline(30, color='#7B858D', ls='--', lw=1.2, label='30 μs reference')
    ax.set_xscale('log')
    ax.set(xlabel='T1 coherence time (μs), with T2 = 2T1/3',
           ylabel='Average gate fidelity (%)',
           title='The decoherence crossover: when longer control becomes worthwhile')
    ax.grid(alpha=.18)
    ax.legend(loc='lower right', fontsize=9)
    savefig(fig, 'coherence_crossover.png')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quick', action='store_true',
                        help='Use fewer scan points for initial validation')
    args = parser.parse_args()
    winner = plot_tradeoff(samples=15 if args.quick else 37)
    counts = plot_map(points=17 if args.quick else 35)
    robust = plot_robust(points=3 if args.quick else 5)
    plot_coherence_crossover(samples=15 if args.quick else 29)
    print('Shortest feasible duration-sweep candidate:',
          winner['sequence'] if winner else 'none')
    print('Nominal robustness winner:', robust['sequence'] if robust else 'none')
    print('Selection-map counts:', counts)
    print('All figures and CSV results saved to', OUT.resolve())


if __name__ == '__main__':
    main()
