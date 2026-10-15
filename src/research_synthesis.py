"""Gridium-inspired robust pulse synthesis for Team Semiclassical.

Numerical optimizer = classical SciPy. Physics = same driven-qubit Lindbladian
and T1/T2 convention as the team's decoherence.pulse_superop. Qiskit reference
checks are provided explicitly; this module is not a hardware pulse scheduler.

Candidate design: five sequential rectangular segments, phase and duration
variable, *fixed* Rabi rate omega=pi/primitive_ns (same as X/BB1/CORPSE).
The optimizer sees only a small TRAIN uncertainty mesh. Evaluation reports a
separate validation mesh used for candidate selection.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
from pathlib import Path

import numpy as np
from scipy.linalg import expm
from scipy.optimize import differential_evolution
from result_provenance import waveform_id

X = np.array([[0., 1.], [1., 0.]], dtype=complex)
Y = np.array([[0., -1j], [1j, 0.]], dtype=complex)
Z = np.diag([1., -1.]).astype(complex)
I2 = np.eye(2, dtype=complex)
TARGET_S = np.kron(X.conj(), X)
PHI_BB1 = np.arccos(-.25)

BASELINES = {
    'primitive': ((np.pi, 0.),),
    'BB1': ((np.pi, 0.), (np.pi, PHI_BB1),
            (2*np.pi, 3*PHI_BB1), (np.pi, PHI_BB1)),
    'CORPSE': ((7*np.pi/3, 0.), (5*np.pi/3, np.pi), (np.pi/3, 0.)),
}


@dataclass(frozen=True)
class Experiment:
    primitive_ns: float = 100.
    t1_ns: float = 200_000.
    t2_ns: float = 150_000.
    amplitude_center: float = .05
    amplitude_width: float = .02
    detuning_center_over_omega: float = 0.
    detuning_width_over_omega: float = .02
    min_fidelity: float = .997
    angle_budget_pi: float = 5.25
    seed: int = 2026

    def __post_init__(self):
        numeric = [self.primitive_ns, self.t1_ns, self.t2_ns,
                   self.amplitude_center, self.amplitude_width,
                   self.detuning_center_over_omega,
                   self.detuning_width_over_omega, self.min_fidelity,
                   self.angle_budget_pi]
        if not all(np.isfinite(x) for x in numeric):
            raise ValueError('Experiment settings must be finite')
        if self.primitive_ns <= 0 or self.t1_ns <= 0 or self.t2_ns <= 0:
            raise ValueError('Pulse and coherence times must be positive')
        if self.t2_ns > 2*self.t1_ns:
            raise ValueError('Require T2 <= 2*T1')
        if not 0 < self.min_fidelity <= 1:
            raise ValueError('min_fidelity must lie in (0,1]')
        if self.amplitude_width < 0 or self.detuning_width_over_omega < 0:
            raise ValueError('Uncertainties must be nonnegative')
        if 1+self.amplitude_center-self.amplitude_width <= 0:
            raise ValueError('Actual drive amplitude must stay positive')
        if self.angle_budget_pi < 1:
            raise ValueError('Angle budget must be at least pi')
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise ValueError('seed must be an integer')

    @property
    def omega(self) -> float:
        return np.pi/self.primitive_ns


def uncertainty_points(ex: Experiment, *, held_out=False):
    """Pairs of (amplitude fraction, normalized detuning).

    Train is a 3x3 Cartesian mesh. Validation uses 72 other 9x9 grid nodes
    and 24 random samples; train points are not reused.
    """
    if held_out:
        # Independent 9x9 grid including physical box boundaries; delete
        # exact training nodes {-1,0,1}x{-1,0,1}.
        axis = np.linspace(-1.,1.,9)
        a, d = np.meshgrid(axis, axis, indexing='ij')
        positions = np.column_stack([a.ravel(),d.ravel()])
        positions = np.array([p for p in positions if not (p[0] in (-1.,0.,1.) and p[1] in (-1.,0.,1.))])
        rng = np.random.default_rng(ex.seed + 739)
        positions = np.vstack((positions, rng.uniform(-1,1,size=(24,2))))
    else:
        a, d = np.meshgrid([-1.,0.,1.], [-1.,0.,1.], indexing='ij')
        positions = np.column_stack([a.ravel(),d.ravel()])
    return np.column_stack((ex.amplitude_center+ex.amplitude_width*positions[:,0],
        ex.detuning_center_over_omega+ex.detuning_width_over_omega*positions[:,1]))


def lindblad_segment(angle: float, phase: float, ex: Experiment,
                     amplitude_error: float, detuning_over_omega: float):
    """4x4 column-vectorized superoperator; exact fixed-H Lindblad evolution."""
    if not (np.isfinite(angle) and np.isfinite(phase) and angle > 0):
        raise ValueError('Segment angles must be positive and finite')
    omega = ex.omega
    h = .5*(omega*(1+amplitude_error)*(np.cos(phase)*X + np.sin(phase)*Y)
             + detuning_over_omega*omega*Z)
    generator = -1j*(np.kron(I2,h) - np.kron(h.T,I2))
    lower = np.array([[0,1],[0,0]], dtype=complex)
    gamma_1 = 1/ex.t1_ns
    gamma_phi = 1/ex.t2_ns - gamma_1/2
    for gamma, jump in ((gamma_1, lower), (gamma_phi/2, Z)):
        jj = jump.conj().T @ jump
        generator += gamma*(np.kron(jump.conj(),jump)
                   -.5*np.kron(I2,jj)-.5*np.kron(jj.T,I2))
    return expm(generator*(angle/omega))


def channel(segments, ex: Experiment, amplitude_error: float,
            detuning_over_omega: float):
    result = np.eye(4,dtype=complex)
    for angle,phase in segments:
        result = lindblad_segment(float(angle),float(phase),ex,
                                  float(amplitude_error),float(detuning_over_omega)) @ result
    return result


def fidelity_from_superop(superop):
    """TP qubit average fidelity to X: (Tr(S_X^dag S)+2)/6.

    Equivalent to qiskit.quantum_info.average_gate_fidelity(SuperOp(S), X).
    """
    f = (np.trace(TARGET_S.conj().T @ superop).real + 2)/6
    return float(np.clip(f,0,1))


def evaluate(segments, ex: Experiment, points):
    if not segments or any((not np.isfinite(a) or a <= 0 or not np.isfinite(p))
                           for a,p in segments):
        raise ValueError('Invalid segments')
    return np.array([fidelity_from_superop(channel(segments,ex,a,d)) for a,d in points])


def segment_duration_ns(segments, ex: Experiment):
    return float(sum(float(a) for a,_ in segments)/ex.omega)


def _decode(vector):
    angles = np.asarray(vector[:5])*np.pi
    phases = np.asarray(vector[5:])
    return tuple((float(a),float(p)) for a,p in zip(angles,phases))


def _score(vector, ex, points):
    segments = _decode(vector)
    cost_pi = float(np.sum(vector[:5]))
    if cost_pi > ex.angle_budget_pi:
        return 10. + 10.*(cost_pi-ex.angle_budget_pi)
    f = evaluate(segments,ex,points)
    # Strong feasibility penalty followed by runtime minimization; the fidelity
    # term differentiates otherwise equally short feasible controls.
    return 90*max(0,ex.min_fidelity - float(np.min(f))) + .018*cost_pi + .12*(1-f.mean())


def _seed_candidates():
    # Every seed is a five-piece parameterization with a fixed drive strength.
    # BB1 splitting preserves the original pulse *exactly* before optimization.
    bb = [(np.pi/2,0.),(np.pi/2,0.),(np.pi,PHI_BB1),
          (2*np.pi,3*PHI_BB1),(np.pi,PHI_BB1)]
    primitive = [(np.pi/5,0.)]*5
    co = [(7*np.pi/6,0.),(7*np.pi/6,0.),(5*np.pi/3,np.pi),
          (np.pi/6,0.),(np.pi/6,0.)]
    def encode(segs):
        return np.array([a/np.pi for a,p in segs] +
                        [((p+np.pi)%(2*np.pi))-np.pi for a,p in segs])
    return [encode(bb),encode(primitive),encode(co)]


def _solver_record(result, ex, train, bounds):
    values = evaluate(_decode(result.x), ex, train)
    lower, upper = np.asarray(bounds).T
    safety_target = min(1., ex.min_fidelity + 3e-5)
    return {
        'success': bool(result.success),
        'status': int(result.status) if hasattr(result, 'status') else None,
        'message': str(result.message),
        'iterations': int(result.nit) if hasattr(result, 'nit') else None,
        'evaluations': int(result.nfev) if hasattr(result, 'nfev') else None,
        'advertised_fidelity_requirement': ex.min_fidelity,
        'slsqp_safety_target': safety_target,
        'training_fidelities': values.tolist(),
        'advertised_fidelity_residuals': (values - ex.min_fidelity).tolist(),
        'slsqp_safety_residuals': (values - safety_target).tolist(),
        'angle_budget_residual_pi': float(ex.angle_budget_pi - sum(result.x[:5])),
        'lower_bound_residuals': (result.x - lower).tolist(),
        'upper_bound_residuals': (upper - result.x).tolist(),
    }


def synthesize(ex: Experiment=Experiment(), *, maxiter=16,
               popsize=5, run_optimizer=True):
    """Deterministic candidate search, no claim of global optimality.

    Returns metadata and candidate metrics. Training and holdout are disjoint.
    """
    train = uncertainty_points(ex)
    held = uncertainty_points(ex,held_out=True)
    seeds = _seed_candidates()
    bounds = [(0.08,2.10)]*5 + [(-np.pi,np.pi)]*5
    proposals = [(f'seed_{i}',seed) for i,seed in enumerate(seeds)]
    solver_reports = {'status': 'not run'}
    if run_optimizer:
        if not isinstance(maxiter,int) or maxiter < 1 or popsize < 3:
            raise ValueError('Invalid optimization budget')
        result = differential_evolution(
            lambda x: _score(x,ex,train), bounds,
            maxiter=maxiter,popsize=popsize,polish=False,
            seed=ex.seed,init='sobol',tol=.001,updating='immediate',workers=1)
        proposals.append(('differential_evolution', result.x))
        # Apply the same bounded SLSQP minimization to all three starting
        # controls. These are distinct local searches, not globally optimal gates.
        # Keeping BB1's historical label preserves saved benchmark provenance.
        from scipy.optimize import minimize
        def fidelity_constraint(x):
            return evaluate(_decode(x),ex,train)-min(1.,ex.min_fidelity+3e-5)
        refinements = {}
        for name, starting_seed in zip(('BB1', 'primitive', 'CORPSE'), seeds):
            adjusted_seed = starting_seed.copy()
            adjusted_seed[:5] /= (1+ex.amplitude_center)
            refined = minimize(lambda x: .01*sum(x[:5]), adjusted_seed,
                method='SLSQP', bounds=bounds,
                constraints=[{'type':'ineq','fun':fidelity_constraint},
                             {'type':'ineq','fun':lambda x: ex.angle_budget_pi-sum(x[:5])}],
                options={'maxiter':65,'ftol':1e-8})
            label = f'{name}_constrained_synthesis'
            proposals.append((label,refined.x))
            refinements[name] = _solver_record(refined,ex,train,bounds)
        solver_reports = {
            'differential_evolution': _solver_record(result, ex, train, bounds),
            'SLSQP': refinements['BB1'],
            'SLSQP_by_seed': refinements,
        }
    candidates=[]
    for label,vec in proposals:
        segs=_decode(vec)
        dur=segment_duration_ns(segs,ex)
        if dur > ex.angle_budget_pi*ex.primitive_ns+1e-7:
            continue
        ftrain=evaluate(segs,ex,train)
        fhold=evaluate(segs,ex,held)
        candidates.append(dict(name=label,segments=[list(p) for p in segs],
            duration_ns=dur,nominal_fidelity=float(evaluate(segs,ex, np.array([[ex.amplitude_center,
                           ex.detuning_center_over_omega]]))[0]),
            train_worst=float(ftrain.min()),heldout_worst=float(fhold.min()),
            heldout_mean=float(fhold.mean()),
            train_pass=bool(ftrain.min() >= ex.min_fidelity-1e-12),
            heldout_pass=bool(fhold.min() >= ex.min_fidelity-1e-12),
            label='synthesized' ))
    # Static references always included, and physically evaluated with identical
    # model + uncertainty points; they are not subject to the five-segment budget.
    calibrated = {f"{k}_calibrated": tuple((a/(1+ex.amplitude_center),p) for a,p in segs) for k,segs in BASELINES.items()}
    for name,segs in {**BASELINES,**calibrated}.items():
        ftrain=evaluate(segs,ex,train)
        fhold=evaluate(segs,ex,held)
        candidates.append(dict(name=name,segments=[list(p) for p in segs],
            duration_ns=segment_duration_ns(segs,ex),
            nominal_fidelity=float(evaluate(segs,ex,np.array([[ex.amplitude_center,
                              ex.detuning_center_over_omega]]))[0]),
            train_worst=float(ftrain.min()),heldout_worst=float(fhold.min()),
            heldout_mean=float(fhold.mean()),
            train_pass=bool(ftrain.min() >= ex.min_fidelity-1e-12),
            heldout_pass=bool(fhold.min() >= ex.min_fidelity-1e-12),
            label='reference'))
    qualifying = [r for r in candidates if r['train_pass'] and r['heldout_pass']]
    winner = min(qualifying,key=lambda r:(r['duration_ns'],-r['heldout_worst'])) if qualifying else None
    report = dict(config=asdict(ex),train_points=train.tolist(),
        heldout_points=held.tolist(), candidates=candidates,
        winner=winner['name'] if winner else None,
        n_train=int(len(train)),n_heldout=int(len(held)),
        optimizer_ran=bool(run_optimizer),maxiter=maxiter,popsize=popsize,
        solver_reports=solver_reports)
    report['waveform_id'] = waveform_id(report)
    return report


def qiskit_reference_check(segments, ex: Experiment, amp: float, det: float):
    """Cross-check own optimization's channel against team's Lindblad/Qiskit."""
    from qiskit.quantum_info import SuperOp, Operator, average_gate_fidelity
    from decoherence import pulse_superop
    product=np.eye(4,dtype=complex)
    for angle,phase in segments:
        product = pulse_superop(float(angle)/ex.omega,ex.omega,float(phase),
            amplitude_error=amp,detuning_rad_per_ns=det*ex.omega,
            t1_ns=ex.t1_ns,t2_ns=ex.t2_ns).data @ product
    ours=channel(segments,ex,amp,det)
    return {'channel_max_abs_error':float(np.max(np.abs(ours-product))),
            'fidelity_difference':float(abs(fidelity_from_superop(ours)-
                 average_gate_fidelity(SuperOp(product),target=Operator(X))))}


def save_report(report,path):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return path
