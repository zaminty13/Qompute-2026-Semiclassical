import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from qiskit.quantum_info import Operator, average_gate_fidelity

from decoherence import sequence_superop
from pulses import (PAULI_X, SEQUENCE_NAMES, _require_finite, _require_scalars,
                    _require_positive_duration,
                    simulate_sequence)


FIELDS = ('case', 'sequence', 'model', 'primitive_duration_ns',
          'total_duration_ns', 'omega_rad_per_ns', 'amplitude_error',
          'detuning_rad_per_ns', 't1_ns', 't2_ns',
          'average_gate_fidelity', 'average_gate_infidelity')
COLORS = ('#2166ac', '#b35806', '#1b7837')
TARGET = Operator(PAULI_X)


def _grid(values, name, positive=False):
    _require_finite(**{name: values})
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size == 0 or (positive and np.any(array <= 0)):
        raise ValueError(f'{name} must be a nonempty one-dimensional grid'
                         + (' of positive values.' if positive else '.'))
    return array


def representative_cases(amplitude_error=.05, detuning_rad_per_ns=.003):
    values = dict(amplitude_error=amplitude_error, detuning_rad_per_ns=detuning_rad_per_ns)
    _require_scalars(**values)
    _require_finite(**values)
    return (('no_control_error', 0., 0.),
            ('amplitude_only', amplitude_error, 0.),
            ('detuning_only', 0., detuning_rad_per_ns))


def comparison_rows(primitive_durations_ns, *, amplitude_error=.05,
                    detuning_rad_per_ns=.003, t1_ns=30000., t2_ns=20000.):
    durations = _grid(primitive_durations_ns, 'primitive_durations_ns', positive=True)
    rows = []
    for case, epsilon, delta in representative_cases(amplitude_error, detuning_rad_per_ns):
        for duration in durations:
            omega = np.pi / duration
            for sequence in SEQUENCE_NAMES:
                coherent = simulate_sequence(sequence, omega, epsilon, delta)
                channel = sequence_superop(sequence, omega, epsilon, delta,
                                            t1_ns=t1_ns, t2_ns=t2_ns)
                fidelity = float(average_gate_fidelity(channel, target=TARGET))
                if not np.isfinite(fidelity) or not -1e-12 <= fidelity <= 1 + 1e-12:
                    raise RuntimeError('Channel fidelity is outside numerical tolerance.')
                for model, f, infidelity, t1, t2 in (
                    ('coherent', coherent.average_gate_fidelity,
                     coherent.average_gate_infidelity, np.inf, np.inf),
                    ('lindblad', fidelity, 1 - fidelity, t1_ns, t2_ns),
                ):
                    rows.append(dict(zip(FIELDS, (case, sequence, model, duration,
                        coherent.total_duration_ns, omega, epsilon, delta, t1, t2,
                        f, infidelity))))
    return rows


def amplitude_rows(amplitude_errors, primitive_duration_ns=100.):
    errors = _grid(amplitude_errors, 'amplitude_errors')
    _require_positive_duration(primitive_duration_ns)
    omega = np.pi / primitive_duration_ns
    rows = []
    for epsilon in errors:
        for sequence in SEQUENCE_NAMES:
            result = simulate_sequence(sequence, omega, epsilon, 0.)
            rows.append(dict(zip(FIELDS, ('amplitude_sensitivity', sequence, 'coherent',
                primitive_duration_ns, result.total_duration_ns, omega, epsilon,
                0., np.inf, np.inf, result.average_gate_fidelity,
                result.average_gate_infidelity))))
    return rows


def write_csv(path, rows):
    if not rows:
        raise ValueError('Cannot write an empty comparison.')
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def _select(rows, sequence, model='coherent', case=None):
    return [r for r in rows if r['sequence'] == sequence and r['model'] == model
            and (case is None or r['case'] == case)]


def _style(ax):
    ax.grid(alpha=.25)
    ax.spines[['top', 'right']].set_visible(False)


def plot_amplitude(rows):
    fig, ax = plt.subplots(figsize=(9, 5.5), layout='constrained')
    for sequence, color, style in zip(SEQUENCE_NAMES, COLORS, ('-', '-', '--')):
        subset = _select(rows, sequence)
        ax.plot([r['amplitude_error'] for r in subset],
                [r['average_gate_infidelity'] for r in subset],
                label=f"{sequence} ({subset[0]['total_duration_ns']:.2f} ns)",
                color=color, linestyle=style, linewidth=2)
    ax.set(xlabel='Fractional amplitude error', ylabel='Average gate infidelity (1 - F)',
           ylim=(0, None), title='Amplitude sensitivity at shared nominal drive\n'
           f"Omega = {rows[0]['omega_rad_per_ns']:.6g} rad/ns; detuning = 0; no decoherence")
    ax.text(.5, .56, 'Primitive and CORPSE overlap', transform=ax.transAxes, ha='center')
    ax.legend()
    _style(ax)
    return fig


def _case_title(row):
    return (row['case'].replace('_', ' ').capitalize()
            + f"\nepsilon = {row['amplitude_error']:g} (fraction), delta = {row['detuning_rad_per_ns']:g} rad/ns")


def plot_comparison(rows):
    cases = list(dict.fromkeys(r['case'] for r in rows))
    fig, axes = plt.subplots(1, len(cases), figsize=(14, 5), sharey=True, layout='constrained', squeeze=False)
    axes = axes.ravel()
    for ax, case in zip(axes, cases):
        for offset, model, hatch, label in ((-.19, 'coherent', '//', 'Coherent only'),
                                            (.19, 'lindblad', '', 'With decoherence')):
            subset = [_select(rows, s, model, case)[0] for s in SEQUENCE_NAMES]
            ax.bar(np.arange(3) + offset, [r['average_gate_infidelity'] for r in subset],
                   width=.36, color=COLORS, hatch=hatch, alpha=.65 if model == 'coherent' else 1,
                   edgecolor='black', linewidth=.5, label=label)
        ax.set_xticks(np.arange(3), [f"{r['sequence']}\n{r['total_duration_ns']:.2f} ns" for r in subset])
        ax.set_title(_case_title(subset[0]))
        _style(ax)
    axes[0].set_ylim(0, max(1e-12, max(r['average_gate_infidelity'] for r in rows) * 1.15))
    axes[0].set_ylabel('Average gate infidelity (1 - F)')
    axes[-1].legend()
    noise = next(r for r in rows if r['model'] == 'lindblad')
    fig.suptitle(f"Shared Omega = {noise['omega_rad_per_ns']:.6g} rad/ns; "
                 f"T1 = {noise['t1_ns']:g} ns, T2 = {noise['t2_ns']:g} ns\n"
                 'Durations below sequence names are actual total durations')
    return fig


def plot_duration(rows, *, actual_duration=False):
    cases = list(dict.fromkeys(r['case'] for r in rows))
    fig, axes = plt.subplots(1, len(cases), figsize=(15, 5.5), sharey=True, layout='constrained', squeeze=False)
    axes = axes.ravel()
    key = 'total_duration_ns' if actual_duration else 'primitive_duration_ns'
    for ax, case in zip(axes, cases):
        for sequence, color, marker in zip(SEQUENCE_NAMES, COLORS, ('o', 's', '^')):
            for model, style in (('coherent', '--'), ('lindblad', '-')):
                subset = _select(rows, sequence, model, case)
                ax.plot([r[key] for r in subset], [r['average_gate_fidelity'] for r in subset],
                        color=color, linestyle=style, marker=marker, markersize=3,
                        markevery=max(1, len(subset) // 7))
        ax.set_title(_case_title(subset[0]))
        ax.set_xlabel('Actual sequence total duration (ns)' if actual_duration
                      else 'Nominal primitive-X duration (ns)')
        _style(ax)
    minimum = min(r['average_gate_fidelity'] for r in rows)
    axes[0].set_ylim(minimum - max(.005, (1 - minimum) * .05), 1.005)
    axes[0].set_ylabel('Average gate fidelity to ideal X')
    handles = [Line2D([0], [0], color=c, marker=m, label=s)
               for s, c, m in zip(SEQUENCE_NAMES, COLORS, ('o', 's', '^'))]
    handles += [Line2D([0], [0], color='black', linestyle=style, label=label)
                for style, label in (('--', 'Coherent only'), ('-', 'With decoherence'))]
    fig.legend(handles=handles, loc='outside lower center', ncol=5)
    noise = next(r for r in rows if r['model'] == 'lindblad')
    fig.suptitle(f"Fixed errors per panel; T1 = {noise['t1_ns']:g} ns, T2 = {noise['t2_ns']:g} ns\n"
                 'Shared Omega = pi / nominal primitive duration; total times: primitive 1x, BB1 5x, CORPSE 13/3x'
                 + ('\nAt the same actual duration, different sequences use different drive strengths.'
                    if actual_duration else ''))
    return fig


def main():
    parser = argparse.ArgumentParser(description='Local two-level pulse comparisons and duration analysis.')
    parser.add_argument('--output-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'results' / 'decoherence')
    parser.add_argument('--primitive-duration-ns', type=float, default=100.)
    parser.add_argument('--amplitude-error', type=float, default=.05)
    parser.add_argument('--detuning-rad-per-ns', type=float, default=.003)
    parser.add_argument('--t1-ns', type=float, default=30000.)
    parser.add_argument('--t2-ns', type=float, default=20000.)
    parser.add_argument('--duration-min-ns', type=float, default=20.)
    parser.add_argument('--duration-max-ns', type=float, default=500.)
    parser.add_argument('--duration-points', type=int, default=81)
    parser.add_argument('--no-show', action='store_true')
    args = parser.parse_args()
    if (args.duration_points < 2 or not np.isfinite(args.duration_min_ns)
            or not np.isfinite(args.duration_max_ns)
            or not 0 < args.duration_min_ns < args.duration_max_ns):
        parser.error('Duration sweep requires 0 < min < max, finite bounds, and at least two points.')
    params = dict(amplitude_error=args.amplitude_error, detuning_rad_per_ns=args.detuning_rad_per_ns,
                  t1_ns=args.t1_ns, t2_ns=args.t2_ns)
    amplitude = amplitude_rows(np.linspace(-.2, .2, 401), args.primitive_duration_ns)
    comparison = comparison_rows([args.primitive_duration_ns], **params)
    duration = comparison_rows(np.linspace(args.duration_min_ns, args.duration_max_ns,
                                           args.duration_points), **params)
    for name, rows in (('amplitude_comparison', amplitude), ('channel_comparison', comparison),
                       ('duration_sweep', duration)):
        write_csv(args.output_dir / f'{name}.csv', rows)
    figures = [('amplitude_comparison', plot_amplitude(amplitude)),
               ('channel_comparison', plot_comparison(comparison)),
               ('duration_nominal', plot_duration(duration)),
               ('duration_actual', plot_duration(duration, actual_duration=True))]
    for name, fig in figures:
        fig.savefig(args.output_dir / f'{name}.png', dpi=180)
    for row in comparison:
        print(f"{row['case']:18s} {row['sequence']:9s} {row['model']:9s} "
              f"total={row['total_duration_ns']:8.3f} ns F={row['average_gate_fidelity']:.10f}")
    print(f'Saved 3 CSVs and 4 figures to {args.output_dir.resolve()}')
    if args.no_show:
        for _, fig in figures:
            plt.close(fig)
    else:
        plt.show()


if __name__ == '__main__':
    main()
