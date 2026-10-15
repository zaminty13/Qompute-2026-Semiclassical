"""Post-selection diagnostics for PulseWise's simulated sampled-fidelity study.

Does not modify optimization results, winners, or saved artifacts.
All stress computations reuse the same two-level physics model, NOT hardware.
"""
from __future__ import annotations
import numpy as np
from research_synthesis import Experiment, evaluate

NEAR_TIE_NS = 0.05  # Interpretation only; the optimizer's ranking is unchanged.


def summarize_selection(report, *, near_tie_ns=NEAR_TIE_NS):
    """Explain stored ranking, reference advantage and solver limitations."""
    candidates = report['candidates']
    passing = [c for c in candidates if c['train_pass'] and c['heldout_pass']]
    winner = next((c for c in candidates if c['name'] == report['winner']), None)
    if winner is not None and winner not in passing:
        raise ValueError('Stored winner did not pass both sampled sets')
    if passing and (winner is None or
        any(c['duration_ns'] < winner['duration_ns'] - 1e-8 for c in passing)):
        raise ValueError('Stored winner is not the shortest sampled-passing candidate')
    references = [c for c in passing if c['name'] in
                  ('primitive', 'BB1', 'CORPSE', 'primitive_calibrated',
                   'BB1_calibrated', 'CORPSE_calibrated')]
    ref = min(references, key=lambda c: c['duration_ns']) if references else None
    report_solvers = report.get('solver_reports', {})
    by_seed = report_solvers.get('SLSQP_by_seed', {})
    solver = None
    if winner is not None:
        suffix = '_constrained_synthesis'
        if winner['name'].endswith(suffix):
            solver = by_seed.get(winner['name'][:-len(suffix)])
        elif winner['name'] == 'differential_evolution':
            solver = report_solvers.get('differential_evolution')
    safety_residual = (min(solver['slsqp_safety_residuals'])
                       if solver and solver.get('slsqp_safety_residuals') else None)
    tied = ([c['name'] for c in passing
             if abs(c['duration_ns'] - winner['duration_ns']) <= near_tie_ns]
            if winner else [])
    segs = winner['segments'] if winner else []
    phases = np.array([p for _, p in segs])
    phases = (phases + np.pi) % (2 * np.pi) - np.pi
    near_single_axis = bool(winner and winner['name'].endswith('_constrained_synthesis')
                            and len(phases) > 0 and np.max(np.abs(phases)) < 0.02)
    return dict(
        winner=winner['name'] if winner else None,
        winner_duration_ns=winner['duration_ns'] if winner else None,
        fastest_passing_reference=ref['name'] if ref else None,
        fastest_passing_reference_ns=ref['duration_ns'] if ref else None,
        reduction_vs_fastest_passing_reference_pct=(
            100 * (1 - winner['duration_ns'] / ref['duration_ns'])
            if winner and ref else None),
        near_tie_ns=near_tie_ns,
        near_tied_candidates=tied,
        winner_solver_success=solver.get('success') if solver else None,
        winner_solver_message=solver.get('message') if solver else None,
        winner_slsqp_safety_min_residual=safety_residual,
        winner_near_single_axis=near_single_axis,
        winner_total_unsigned_angle_over_pi=(
            sum(a for a, _ in segs) / np.pi if segs else None),
        differential_evolution_converged=report_solvers.get(
            'differential_evolution', {}).get('success'),
    )


def independent_sample_stress(report, *, grid_size=19, random_count=128, seed=61423):
    """Probe fresh in-box samples not used to fit OR select candidates.

    Not a different physics model, a continuous bound, or hardware validation.
    """
    if grid_size < 5 or random_count < 0:
        raise ValueError('Invalid extra stress sampling size')
    ex = Experiment(**report['config'])
    ca, wa = ex.amplitude_center, ex.amplitude_width
    cd, wd = ex.detuning_center_over_omega, ex.detuning_width_over_omega
    aa, dd = np.meshgrid(np.linspace(ca-wa, ca+wa, grid_size),
                         np.linspace(cd-wd, cd+wd, grid_size), indexing='ij')
    grid = np.column_stack((aa.ravel(), dd.ravel()))
    rng = np.random.default_rng(seed)
    random = np.column_stack((rng.uniform(ca-wa, ca+wa, random_count),
                              rng.uniform(cd-wd, cd+wd, random_count)))
    points = np.vstack((grid, random))
    excluded = np.asarray(report['train_points'] + report['heldout_points'], dtype=float)
    mask = ~np.any(np.all(np.isclose(points[:, None, :], excluded[None, :, :],
                                      atol=1e-12, rtol=0), axis=2), axis=1)
    points = points[mask]
    if len(points) == 0:
        raise ValueError('No new stress points')
    selection = summarize_selection(report)
    names = set(selection['near_tied_candidates'])
    names.add(report['winner'])
    names.add(selection['fastest_passing_reference'])
    names.discard(None)
    results = []
    for c in report['candidates']:
        if c['name'] not in names:
            continue
        values = evaluate(c['segments'], ex, points)
        i = int(np.argmin(values))
        results.append(dict(candidate=c['name'], worst_fidelity=float(values[i]),
                            mean_fidelity=float(values.mean()),
                            pass_stress=bool(values[i] >= ex.min_fidelity-1e-12),
                            below_threshold_count=int((values < ex.min_fidelity-1e-12).sum()),
                            worst_point=points[i].tolist()))
    return dict(total_points=int(len(points)), grid_size=grid_size,
                random_requested=random_count, seed=seed,
                points_reused_from_training_or_selection=0,
                reference_model='same two-level Lindblad model',
                threshold=ex.min_fidelity, candidates=results,
                disclaimer='Sample-based in-model stress only; no continuous or hardware certification.')
