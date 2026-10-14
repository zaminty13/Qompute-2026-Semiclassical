import argparse
import csv
from datetime import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import time

import numpy as np
from qiskit.quantum_info import Operator, average_gate_fidelity
from scipy.optimize import brentq

from decoherence import sequence_superop
from pulses import PAULI_X, sequence_duration_ns, sequence_unitary


ROOT = Path(__file__).resolve().parents[1]
OMEGA = np.pi / 100.
FIDELITY_TOL = 1e-10
ROOT_XTOL = 1e-12
ROOT_RTOL = 1e-12
CASES = {'stronger': (15000., 10000.), 'baseline': (30000., 20000.),
         'weaker': (60000., 40000.), 'coherent': (np.inf, np.inf)}
MODES = {'amplitude': ('BB1', 0., .2), 'detuning': ('CORPSE', -.01, .01)}
TARGET = Operator(PAULI_X)


def preference(difference, tolerance=FIDELITY_TOL):
    if not np.isfinite(difference) or not np.isfinite(tolerance) or tolerance < 0:
        raise ValueError('Difference and tolerance must be finite; tolerance must be nonnegative.')
    return 'composite' if difference > tolerance else 'primitive' if difference < -tolerance else 'tie'


def evaluate_pair(mode, case, coordinate):
    composite = MODES[mode][0]
    t1, t2 = CASES[case]
    epsilon, delta = (coordinate, 0.) if mode == 'amplitude' else (0., coordinate)
    fidelities = []
    for sequence in ('primitive', composite):
        operation = (Operator(sequence_unitary(sequence, OMEGA, epsilon, delta))
                     if case == 'coherent' else
                     sequence_superop(sequence, OMEGA, epsilon, delta, t1_ns=t1, t2_ns=t2))
        value = float(average_gate_fidelity(operation, target=TARGET))
        if not np.isfinite(value) or not -1e-12 <= value <= 1 + 1e-12:
            raise RuntimeError('Invalid fidelity from simulator.')
        fidelities.append(value)
    return dict(mode=mode, case=case, coordinate=coordinate,
                coordinate_unit='fraction' if mode == 'amplitude' else 'rad/ns',
                amplitude_error=epsilon, amplitude_error_percent=100 * epsilon,
                detuning_rad_per_ns=delta, delta_over_omega=delta / OMEGA,
                nominal_primitive_duration_ns=100., omega_rad_per_ns=OMEGA,
                t1_ns=t1, t2_ns=t2, primitive_sequence='primitive', composite_sequence=composite,
                primitive_duration_ns=sequence_duration_ns('primitive', OMEGA),
                composite_duration_ns=sequence_duration_ns(composite, OMEGA),
                primitive_fidelity=fidelities[0], composite_fidelity=fidelities[1],
                delta_f=fidelities[1] - fidelities[0],
                preferred=preference(fidelities[1] - fidelities[0]))


def validate_grid(grid, values):
    grid, values = np.asarray(grid), np.asarray(values)
    if (grid.ndim != 1 or values.shape != grid.shape or grid.size < 2
            or not np.all(np.isfinite(grid)) or not np.all(np.isfinite(values))
            or not np.all(np.diff(grid) > 0)):
        raise ValueError('Expected finite samples on a strictly increasing grid.')
    return grid, values


def find_crossovers(function, grid, values, tolerance=FIDELITY_TOL):
    grid, values = validate_grid(grid, values)
    significant = np.flatnonzero(np.abs(values) > tolerance)
    roots = []
    for i, j in zip(significant[:-1], significant[1:]):
        if np.signbit(values[i]) == np.signbit(values[j]):
            continue
        left, right = float(grid[i]), float(grid[j])
        root = brentq(function, left, right, xtol=ROOT_XTOL, rtol=ROOT_RTOL)
        left_value, right_value, residual = function(left), function(right), function(root)
        if (preference(left_value, tolerance) == preference(right_value, tolerance)
                or abs(left_value) <= tolerance or abs(right_value) <= tolerance
                or abs(residual) > tolerance):
            raise RuntimeError('Crossover failed fresh simulator checks.')
        roots.append(dict(coordinate=root, bracket_left=left, bracket_right=right,
                          left_delta_f=left_value, right_delta_f=right_value,
                          left_preferred=preference(left_value, tolerance),
                          right_preferred=preference(right_value, tolerance), residual=residual))
    return roots


def favorable_intervals(function, grid, values, tolerance=FIDELITY_TOL):
    grid, values = validate_grid(grid, values)
    boundaries = [float(grid[0]), float(grid[-1])]
    for level in (-tolerance, tolerance):
        shifted = values - level
        boundaries.extend(float(grid[i]) for i in np.flatnonzero(shifted == 0))
        for i in np.flatnonzero(np.signbit(shifted[:-1]) != np.signbit(shifted[1:])):
            boundaries.append(brentq(lambda x: function(x) - level, grid[i], grid[i + 1],
                                     xtol=ROOT_XTOL, rtol=ROOT_RTOL))
    boundaries = sorted(set(boundaries))
    intervals = []
    for left, right in zip(boundaries[:-1], boundaries[1:]):
        midpoint = (left + right) / 2
        winner = preference(function(midpoint), tolerance)
        if intervals and intervals[-1]['preferred'] == winner:
            intervals[-1]['right'] = right
        else:
            intervals.append(dict(left=left, right=right, preferred=winner))
    return intervals


def write_rows(path, rows):
    with path.open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def make_plots(output, data, crossovers, no_show):
    import matplotlib
    if no_show:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    for mode, (composite, _, _) in MODES.items():
        fig, axes = plt.subplots(2, 1, figsize=(9, 8), sharex=True, layout='constrained')
        for case, style in (('baseline', '-'), ('coherent', '--')):
            rows = data[mode, case]
            x = [r['coordinate'] for r in rows]
            for sequence, color in (('primitive', '#2166ac'), ('composite', '#b35806')):
                name = 'primitive' if sequence == 'primitive' else composite
                axes[0].plot(x, [r[f'{sequence}_fidelity'] for r in rows], color=color,
                             linestyle=style, label=f'{name}: {case}')
            axes[1].plot(x, [r['delta_f'] for r in rows], linestyle=style,
                         label=f'{case}: {composite} - primitive')
        for row in crossovers:
            if row['mode'] == mode and row['case'] == 'baseline':
                axes[1].plot(row['coordinate'], 0, 'ko')
                for ax in axes:
                    ax.axvline(row['coordinate'], color='gray', alpha=.5, linestyle=':')
        axes[0].set_ylabel('Average gate fidelity to ideal X')
        axes[1].set_ylabel('Delta F (positive favors composite)')
        axes[1].axhline(0, color='black', linewidth=.8)
        xlabel = ('Fractional amplitude error (0.05 = 5%)' if mode == 'amplitude'
                  else 'Absolute detuning delta (rad/ns)')
        axes[1].set_xlabel(xlabel)
        secondary = axes[0].secondary_xaxis('top', functions=(
            (lambda x: x * 100), (lambda x: x / 100)) if mode == 'amplitude' else (
            (lambda x: x / OMEGA), (lambda x: x * OMEGA)))
        secondary.set_xlabel('Amplitude error (%)' if mode == 'amplitude' else 'Relative detuning delta / Omega')
        for ax in axes:
            ax.grid(alpha=.25)
            ax.legend(fontsize=9)
        fixed = 'detuning = 0' if mode == 'amplitude' else 'amplitude error = 0'
        fig.suptitle(f'{composite} crossover: baseline noise versus coherent limit\n'
                     f'T1 = 30,000 ns; T2 = 20,000 ns; {fixed}\n'
                     f'Shared Omega = pi/100 rad/ns; total times: primitive 100 ns, '
                     f'{composite} {sequence_duration_ns(composite, OMEGA):.3f} ns')
        fig.savefig(output / f'{mode}_crossover.png', dpi=160)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), layout='constrained')
    for ax, mode in zip(axes, MODES):
        for case, color in zip(CASES, ('#b2182b', '#2166ac', '#1b7837', '#555555')):
            rows = data[mode, case]
            t1, t2 = CASES[case]
            label = 'Coherent only' if case == 'coherent' else f'{case}: T1/T2 = {t1:g}/{t2:g} ns'
            ax.plot([r['coordinate'] for r in rows], [r['delta_f'] for r in rows],
                    label=label, color=color, linestyle='--' if case == 'coherent' else '-')
            roots = [r['coordinate'] for r in crossovers if r['mode'] == mode and r['case'] == case]
            ax.scatter(roots, np.zeros(len(roots)), color=color, s=30, zorder=4)
        ax.axhline(0, color='black', linewidth=.8)
        ax.set_title(f'{MODES[mode][0]} minus primitive')
        ax.set_xlabel('Fractional amplitude error (0.05 = 5%)' if mode == 'amplitude'
                      else 'Absolute detuning delta (rad/ns)')
        ax.set_ylabel('Delta F (positive favors composite)')
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    fig.suptitle('Coherence-time dependence at shared Omega = pi/100 rad/ns\n'
                 'Actual times: primitive 100 ns, BB1 500 ns, CORPSE 433.333 ns; dots mark order changes')
    fig.savefig(output / 'coherence_dependence.png', dpi=160)
    if no_show:
        plt.close('all')
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description='Evaluate pairwise X-gate crossovers without changing existing results.')
    parser.add_argument('--points', type=int, default=1001)
    parser.add_argument('--run-name', default='day2')
    parser.add_argument('--no-show', action='store_true')
    args = parser.parse_args()
    if args.points < 3 or not re.fullmatch(r'[A-Za-z0-9_-]+', args.run_name):
        parser.error('Use at least 3 grid points and a run name containing only letters, digits, _ or -.')
    output = ROOT / 'results' / 'decoherence' / 'exploration' / args.run_name
    if output.exists():
        output = output.with_name(args.run_name + '_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    output.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()
    data, roots_all, intervals_all, validation = {}, [], [], []
    for mode, (_, low, high) in MODES.items():
        for case in CASES:
            function = lambda x: evaluate_pair(mode, case, float(x))['delta_f']
            detected = []
            for points in (args.points, 2 * args.points - 1):
                grid = np.linspace(low, high, points)
                rows = [evaluate_pair(mode, case, float(x)) for x in grid]
                values = np.array([r['delta_f'] for r in rows])
                roots = find_crossovers(function, grid, values)
                detected.append(roots)
                write_rows(output / f'{mode}_{case}_{points}.csv', rows)
            coarse, fine = detected
            if len(coarse) != len(fine) or not np.allclose(
                    [r['coordinate'] for r in coarse], [r['coordinate'] for r in fine], atol=1e-10, rtol=0):
                raise RuntimeError('Grid refinement changed detected crossovers; inspect and refine further.')
            data[mode, case] = rows
            validation.append(dict(mode=mode, case=case, coarse_roots=len(coarse), fine_roots=len(fine),
                coarse_spacing=(high-low)/(args.points-1), fine_spacing=(high-low)/(2*args.points-2),
                root_shift_max=max((abs(a['coordinate']-b['coordinate']) for a,b in zip(coarse,fine)), default=0.),
                tolerance_tie_samples=int(np.sum(np.abs(values) <= FIDELITY_TOL))))
            for root in fine:
                row = evaluate_pair(mode, case, root['coordinate'])
                row.update(root)
                roots_all.append(row)
            for interval in favorable_intervals(function, grid, values):
                intervals_all.append(dict(mode=mode, case=case, **interval))
            print(f'{mode} {case}: {len(fine)} crossovers at {[r["coordinate"] for r in fine]}', flush=True)
    write_rows(output / 'crossovers.csv', roots_all)
    write_rows(output / 'intervals.csv', intervals_all)
    write_rows(output / 'grid_validation.csv', validation)
    make_plots(output, data, roots_all, args.no_show)
    command = f'.\\.venv\\Scripts\\python.exe src\\analyze_crossovers.py --points {args.points} --run-name {args.run_name} --no-show'
    metadata = dict(nominal_primitive_duration_ns=100., omega_rad_per_ns=OMEGA,
        cases={k: [str(t1), str(t2)] for k,(t1,t2) in CASES.items()},
        modes=MODES, coarse_points=args.points, fine_points=2*args.points-1,
        fidelity_tolerance=FIDELITY_TOL, root_absolute_tolerance=ROOT_XTOL,
        root_relative_tolerance=ROOT_RTOL, grid_validation=validation,
        reproduction_command=command, elapsed_seconds=time.perf_counter()-started,
        versions={p: importlib.metadata.version(p) for p in ('numpy','scipy','qiskit','matplotlib')},
        source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in (ROOT/'src'/'pulses.py', ROOT/'src'/'decoherence.py', Path(__file__))})
    (output / 'metadata.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    (output / 'analysis_notes.md').write_text(
        '# Crossover analysis\n\nIllustrative two-level X-gate simulations; not hardware measurements.\n\n'
        'Delta F = F_composite - F_primitive. A difference within 1e-10 is a numerical tie. '
        'Root tolerance is 1e-12 in the coordinate units (fraction or rad/ns), with rtol 1e-12. '
        'Significant opposite signs bracket roots; exact ties and touches are not counted as order changes.\n\n'
        'crossovers.csv includes both fidelities, durations, refined coordinates, and fresh simulator '
        'evaluations at the bracket endpoints on either side. intervals.csv uses refined +/-1e-10 '
        'boundaries: endpoints at these thresholds belong to the tie band. Domain endpoints are included. '
        'Intervals are inferred from samples and fresh midpoint checks, not proven analytically. '
        'The finer-grid check is numerical evidence, not a guarantee against unobserved narrow features.\n\n'
        'Coherent-only uses the existing unitary simulator and Qiskit fidelity. Every noisy result uses '
        'the complete Lindblad SuperOp. Positive and negative detuning are evaluated independently. '
        'T1/T2 scale together; the coherent limit is separate. Shared drive means actual durations '
        '100 ns (primitive), 500 ns (BB1), and 433.333333 ns (CORPSE).\n\n'
        'Each sweep CSV contains paired fidelities, parameters, units, sequence names and durations. '
        'Coarse and fine files retain both independently evaluated grids. Metadata records versions, '
        'source hashes, spacing checks and tolerances. Existing output directories are never overwritten; '
        'a repeated run gets a timestamp suffix.\n\n'
        'From the repository root in PowerShell:\n\n```powershell\n' + command + '\n```\n', encoding='utf-8')
    print(f'Outputs: {output}\nElapsed: {metadata["elapsed_seconds"]:.2f} s', flush=True)


if __name__ == '__main__':
    main()
