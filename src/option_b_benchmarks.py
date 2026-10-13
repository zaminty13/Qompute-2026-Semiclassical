"""Reproducible PulseWise cross-model and known-answer circuit benchmarks.

All four candidates are subjected to the *same* controls and model settings.
Two-level X-channel experiments include Markovian T1/T2 and quasi-static
control biases; the four-level coherent surrogate omits T1/T2. Those models
must NEVER be interpreted as physically identical or directly comparable.

The parity experiment assumes IDEAL CNOT gates, measurement and initialization.
Only the data-register X-pulse preparations are noisy. This limitation is
intentional and must be disclosed to judges.
"""
from __future__ import annotations

from itertools import product

import numpy as np

from research_synthesis import BASELINES, Experiment, X, channel, segment_duration_ns
from research_leakage import propagate

CANDIDATES = ('primitive', 'BB1', 'CORPSE', 'synthesized')
LABELS = {'primitive': 'Primitive X', 'BB1': 'BB1',
          'CORPSE': 'CORPSE', 'synthesized': 'Synthesized'}


def candidate_segments(report):
    """Recover the exact 4 comparison controls from the frozen optimizer report.

    The synthesized pulse is *not* replaced by a reference if optimization
    fails; in that case we stop rather than mislabel a standard sequence.
    """
    if not isinstance(report, dict) or 'candidates' not in report:
        raise ValueError('A complete optimization report is required')
    segments = {name: BASELINES[name] for name in ('primitive', 'BB1', 'CORPSE')}
    synthesized = [r for r in report['candidates']
                   if r['name'] == 'BB1_constrained_synthesis'
                   and r.get('label') == 'synthesized']
    if len(synthesized) != 1:
        raise ValueError('Missing unique BB1_constrained_synthesis candidate')
    segments['synthesized'] = tuple(tuple(float(x) for x in item)
                                     for item in synthesized[0]['segments'])
    if len(segments['synthesized']) != 5:
        raise ValueError('Synthesized control must have five segments')
    return segments


def shared_multilevel_comparison(report, *, primitive_ns=100.,
                                  anharmonicity_over_omega=-3.,
                                  coupling_ratio=np.sqrt(2),
                                  amplitude_error=0.,
                                  detuning_over_omega=0.,
                                  steps_per_segment=18):
    """Matched 4-control coherent 4D surrogate comparison.

    Controls may have different durations by design but share Omega, eta,
    alpha/Omega, amplitude bias, detuning and initial logical states.
    """
    ex = Experiment(**report['config'])
    if not np.isclose(primitive_ns, ex.primitive_ns):
        raise ValueError('Do not silently change the drive-speed calibration')
    rows=[]
    for name,segments in candidate_segments(report).items():
        out=propagate(segments, primitive_ns=primitive_ns,
                      anharmonicity_over_omega=anharmonicity_over_omega,
                      coupling_ratio=coupling_ratio,
                      amplitude_error=amplitude_error,
                      detuning_over_omega=detuning_over_omega,
                      steps_per_segment=steps_per_segment)
        rows.append({'candidate':name, 'label':LABELS[name],
                     'duration_ns':out['duration_ns'],
                     'segments':len(segments),
                     'fidelity_unconditional':out['fidelity_unconditional'],
                     'final_leakage':out['final_leakage'],
                     'peak_leakage':out['peak_leakage']})
    return rows


def multilevel_sweep(report, *, alphas=(-8.,-6.,-4.,-3.,-2.,-1.),
                     coupling_ratio=np.sqrt(2), amplitude_error=0.,
                     detuning_over_omega=0.):
    rows=[]
    for alpha in alphas:
        for row in shared_multilevel_comparison(
                report, anharmonicity_over_omega=float(alpha),
                coupling_ratio=coupling_ratio,amplitude_error=amplitude_error,
                detuning_over_omega=detuning_over_omega,
                steps_per_segment=12):
            rows.append({'alpha_over_omega':float(alpha),**row})
    return rows


def _density_zero():
    rho = np.array([[1.,0.],[0.,0.]], dtype=complex)
    return rho.reshape(4,order='F')


def identity_circuit_success(s: np.ndarray, depth: int):
    """Known-answer X^depth |0>: expected measurement = depth modulo 2.

    Each pulse uses the same quasi-static control-bias realization.
    Lindblad noise is included in the pulse superoperator at *full* duration.
    """
    if not isinstance(depth,int) or isinstance(depth,bool) or depth < 0:
        raise ValueError('depth must be a nonnegative integer')
    s=np.asarray(s,dtype=complex)
    if s.shape != (4,4):
        raise ValueError('Expected a 4x4 column-vectorized superoperator')
    rho=np.linalg.matrix_power(s,depth) @ _density_zero()
    rho=rho.reshape((2,2),order='F')
    outcome=depth%2
    p=float(np.real(rho[outcome,outcome]))
    if not np.isfinite(p) or p < -1e-7 or p > 1+1e-7:
        raise ValueError('Channel produced unphysical probabilities')
    return float(np.clip(p,0.,1.))


def parity_truth_table_success(s: np.ndarray, nbits=3):
    """Exact correctness of the n-bit parity circuit, with ideal CNOTs.

    Circuit: prepare each one bit via noisy X; CNOT every bit into a clean
    ancilla; measure ancilla and compare to XOR(input). Inputs are uniform.

    A bit prepared as zero is left idle *without noise*. Input bits are
    independent. Coherences do not affect the measured ancilla Z-parity.
    """
    if not isinstance(nbits,int) or isinstance(nbits,bool) or not 1<=nbits<=8:
        raise ValueError('nbits must be 1..8')
    p_correct_one=identity_circuit_success(s,1)
    error=1.-p_correct_one
    rows=[]
    for bits in product((0,1), repeat=nbits):
        k=sum(bits)
        success=.5*(1.+(1.-2.*error)**k)
        rows.append({'input_bits':''.join(map(str,bits)),
                     'expected_parity':k%2,'x_gates':k,
                     'success_probability':float(success)})
    return {'mean_success':float(np.mean([r['success_probability'] for r in rows])),
            'truth_table':rows, 'nbits':nbits,
            'expected_x_gates':float(nbits/2.)}


def circuit_depth_benchmark(report, *, depths=(1,2,4,8,16,32),
                            cases=None):
    """Matched 2-level noise experiments + shot-independent exact predictions."""
    ex=Experiment(**report['config'])
    depths=tuple(depths)
    if not depths or any(not isinstance(d,int) or isinstance(d,bool) or d<1 for d in depths):
        raise ValueError('Require positive integer depths')
    if cases is None:
        cases={'zero systematic bias':(0.,0.),
               'amplitude +5%':(.05,0.),
               'detuning +0.04 Ω':(0.,.04),
               'combined corner':(.05,.04)}
    controls=candidate_segments(report)
    rows=[]
    for case,(amp,det) in cases.items():
        for name,segments in controls.items():
            s=channel(segments,ex,float(amp),float(det))
            parity=parity_truth_table_success(s)
            for depth in depths:
                rows.append({'case':str(case),'amplitude_error':float(amp),
                             'detuning_over_omega':float(det),'candidate':name,
                             'depth':depth,
                             'success_probability':identity_circuit_success(s,depth),
                             'parity_3bit_mean_success':parity['mean_success'],
                             'total_duration_ns':float(depth*segment_duration_ns(segments,ex)),
                             'total_segments':int(depth*len(segments)),
                             'assumption':'Only X pulses noisy; ideal state preparation/measurement and CNOTs'})
    return rows


def stress_test_report(report, *, grid_size=21, n_random=256, seed=88231):
    """Frozen waveform checked outside its optimizer train/holdout set.

    The dense grid and RNG seed differ from those in research_synthesis.py.
    An extra shifted box is deliberately OUTSIDE the training uncertainty box.
    """
    from research_synthesis import evaluate
    ex=Experiment(**report['config'])
    if not isinstance(grid_size,int) or grid_size<3 or grid_size>101:
        raise ValueError('grid_size must be between 3 and 101')
    if not isinstance(n_random,int) or n_random<16 or n_random>100000:
        raise ValueError('n_random must be between 16 and 100000')
    grid=np.linspace(-1.,1.,grid_size)
    grid_points=np.array([(a,d) for a in grid for d in grid])
    rng=np.random.default_rng(seed)
    held=rng.uniform(-1.,1.,size=(n_random,2))
    shifted=rng.uniform(-1.,1.,size=(n_random,2))
    def make(positions,shift=(0.,0.)):
        return np.column_stack((ex.amplitude_center+shift[0]+ex.amplitude_width*positions[:,0],
                        ex.detuning_center_over_omega+shift[1]+ex.detuning_width_over_omega*positions[:,1]))
    # Small but nontrivial OOD calibration drift.
    suites={'dense_in_domain':make(grid_points),
            'new_random_in_domain':make(held),
            'shifted_calibration_out_of_domain':make(shifted,(.025,.02))}
    rows=[]
    for scenario,points in suites.items():
        for name,segments in candidate_segments(report).items():
            values=evaluate(segments,ex,points)
            rows.append({'scenario':scenario,'candidate':name,'n_points':len(points),
                         'min_fidelity':float(values.min()),
                         'mean_fidelity':float(values.mean()),
                         'p01_fidelity':float(np.quantile(values,.01)),
                         'fraction_below_threshold':float(np.mean(values<ex.min_fidelity)),
                         'passes_all_sampled':bool(np.all(values>=ex.min_fidelity))})
    return rows


def qiskit_aer_circuit_checks(report, *, shots=2048, seed=2026,
                              amplitude_error=.05,detuning_over_omega=.04,
                              depth=16):
    """Optional Qiskit Aer *sampling* check, not hardware verification.

    Tests two circuits for each candidate: X^depth identity/survival and
    the 3-qubit parity algorithm truth table (8 input words).
    """
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import SuperOp
    from qiskit_aer import AerSimulator
    if not isinstance(shots,int) or isinstance(shots,bool) or shots < 128 or shots>100000:
        raise ValueError('shots must be 128..100000')
    if not isinstance(depth,int) or depth<1 or depth>100:
        raise ValueError('depth must be 1..100')
    ex=Experiment(**report['config'])
    sim=AerSimulator(method='density_matrix')
    controls=candidate_segments(report)
    circuits=[];metadata=[];expected=[]
    # Include a genuine IDEAL circuit baseline in the same Qiskit job,
    # in addition to every noisy/suppressed pulse candidate.
    for name in ('ideal', *tuple(controls)):
        if name == 'ideal':
            s=np.kron(X.conj(),X)
            gate=None
        else:
            s=channel(controls[name],ex,amplitude_error,detuning_over_omega)
            gate=SuperOp(s).to_instruction()
        q=QuantumCircuit(1,1)
        for _ in range(depth):
            if gate is None:
                q.x(0)
            else:
                q.append(gate,[0])
        q.measure(0,0)
        circuits.append(q)
        metadata.append((name,'identity',str(depth%2)))
        expected.append(identity_circuit_success(s,depth))
        # 3 data qubits + 1 ancilla, ideal CNOTs.
        for bits in product((0,1),repeat=3):
            q=QuantumCircuit(4,1)
            for k,b in enumerate(bits):
                if b:
                    if gate is None:
                        q.x(k)
                    else:
                        q.append(gate,[k])
            q.cx(0,3)
            q.cx(1,3)
            q.cx(2,3)
            q.measure(3,0)
            circuits.append(q)
            metadata.append((name,''.join(map(str,bits)),str(sum(bits)%2)))
            k=sum(bits)
            error=1.-identity_circuit_success(s,1)
            expected.append(float(.5*(1+(1-2*error)**k)))
    result=sim.run(circuits,shots=shots,seed_simulator=seed).result()
    results=[]
    for i,(name,task,bit) in enumerate(metadata):
        p=result.get_counts(i).get(bit,0)/shots
        sigma=np.sqrt(expected[i]*(1-expected[i])/shots)
        results.append({'candidate':name,'task':task,'expected_bit':bit,
                        'predicted_probability':float(expected[i]),
                        'aer_shot_probability':float(p),
                        'estimated_shot_standard_error':float(sigma),
                        'within_5_sigma_plus_sampling_floor':bool(abs(p-expected[i]) <= 5*sigma+5/shots)})
    return {'shots_per_circuit':shots,'num_circuits':len(circuits),
            'cases':results,'all_consistent':all(v['within_5_sigma_plus_sampling_floor'] for v in results),
            'caveat':'Same modeled channels supplied to Aer; no independent physics/hardware validation.'}
