"""A transparent 4D/two-qubit surrogate illustrating multilevel leakage.

Logical states are basis indices |00> (0), |01> (1); leakage is |10> (2).
|11> (3) is a decoupled spectator to permit a unitary 2-qubit Qiskit circuit.
This is not Gridium's netlist Hamiltonian, nor a calibrated transmon model.
It illustrates the multilevel control/peak-leakage considerations Gridium uses.
No decoherence is included: multilevel and two-level comparisons use separately
identified assumptions rather than silently conflating physical models.
"""
from __future__ import annotations

import numpy as np
from scipy.linalg import expm


def _params(primitive_ns, anharmonicity_over_omega, coupling_ratio,
            amp_error, detuning_over_omega):
    vals=(primitive_ns,anharmonicity_over_omega,coupling_ratio,
          amp_error,detuning_over_omega)
    if not all(np.isfinite(z) for z in vals) or primitive_ns <= 0 or coupling_ratio < 0:
        raise ValueError('Invalid finite model parameters')


def hamiltonian(omega: float, phase: float, amp_error: float,
                detuning_over_omega: float, anharmonicity_over_omega: float,
                coupling_ratio: float):
    """Rotating-frame driven ladder with a spectator.

    Logical 0/1 splitting has the team's Δ Z / 2 convention up to an
    irrelevant global shift. Off-resonant 1-2 coupling scales with eta Ω.
    """
    drive=omega*(1+amp_error)/2
    delta=omega*detuning_over_omega
    alpha=omega*anharmonicity_over_omega
    h=np.diag([0.,-delta,alpha-2*delta,10*omega]).astype(complex)
    e=np.exp(-1j*phase)
    h[0,1]=drive*e
    h[1,0]=np.conj(h[0,1])
    h[1,2]=coupling_ratio*drive*e
    h[2,1]=np.conj(h[1,2])
    return h


def propagate(segments, *, primitive_ns=100., anharmonicity_over_omega=-3.0,
              coupling_ratio=np.sqrt(2), amplitude_error=0.,
              detuning_over_omega=0., steps_per_segment=18):
    """Propagate all logical basis vectors, track mean leakage over both.

    F_unconditional=(Tr(A†A)+|Tr(X†A)|²)/6 with A=P U P (2x2),
    the Haar-average overlap with the ideal X, counting leakage as failure.
    """
    _params(primitive_ns,anharmonicity_over_omega,coupling_ratio,
            amplitude_error,detuning_over_omega)
    if not isinstance(steps_per_segment,int) or steps_per_segment < 2:
        raise ValueError('steps_per_segment must be integer >= 2')
    omega=np.pi/primitive_ns
    u=np.eye(4,dtype=complex)
    times=[0.]
    trace=[0.]
    pop2_0=[0.]
    pop2_1=[0.]
    t=0.
    for angle,phase in segments:
        if not np.isfinite(angle) or angle <= 0 or not np.isfinite(phase):
            raise ValueError('All segments must have finite positive angles')
        dt=float(angle)/(omega*steps_per_segment)
        h=hamiltonian(omega,float(phase),amplitude_error,
                detuning_over_omega,anharmonicity_over_omega,coupling_ratio)
        step=expm(-1j*h*dt)
        for _ in range(steps_per_segment):
            u=step @ u
            t+=dt
            times.append(t)
            pop2_0.append(float(np.abs(u[2,0])**2))
            pop2_1.append(float(np.abs(u[2,1])**2))
            leak0=1-float(np.sum(np.abs(u[:2,0])**2))
            leak1=1-float(np.sum(np.abs(u[:2,1])**2))
            trace.append(float(np.clip(.5*(leak0+leak1),0,1)))
    block=u[:2,:2]
    logical_x=np.array([[0,1],[1,0]],dtype=complex)
    survival=float(np.trace(block.conj().T@block).real/2)
    overlap=abs(np.trace(logical_x.conj().T@block))**2
    f=(np.trace(block.conj().T@block).real+overlap)/6
    return {
        'duration_ns':float(t),
        'fidelity_unconditional':float(np.clip(f,0,1)),
        'final_leakage':float(np.clip(1-survival,0,1)),
        'peak_leakage':max(trace),
        'steps_per_segment':steps_per_segment,
        'times_ns':times,
        'mean_leakage':trace,
        'leak_state_population_if_zero':pop2_0,
        'leak_state_population_if_one':pop2_1,
        'unitary':u,
    }


def qiskit_sample_leakage(unitary,shots=4096,seed=2026):
    """Run 2-qubit Qiskit Aer circuits; compare sample leakage with exact U."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Operator
    from qiskit_aer import AerSimulator
    u=np.asarray(unitary,dtype=complex)
    if u.shape!=(4,4) or not np.allclose(u.conj().T@u,np.eye(4),atol=1e-9):
        raise ValueError('Expected valid 4x4 unitary')
    if not isinstance(shots,int) or isinstance(shots,bool) or not 64<=shots<=100000:
        raise ValueError('shots must be integer from 64 to 100000')
    circuits=[]
    for j in range(2):
        qc=QuantumCircuit(2,2)
        if j:
            qc.x(0)  # logical state |01>, index 1
        qc.unitary(Operator(u),[0,1], label='4-level surrogate')
        qc.measure([0,1],[0,1])
        circuits.append(qc)
    sim=AerSimulator(method='statevector')
    result=sim.run(circuits,shots=shots,seed_simulator=seed).result()
    rows=[]
    for j in range(2):
        counts=result.get_counts(j)
        successes=sum(counts.get(x,0) for x in ('10','11'))
        exact=1-float(np.sum(np.abs(u[:2,j])**2))
        rows.append(dict(input_logical=j,estimated_leakage=successes/shots,
                         exact_leakage=exact,leakage_counts=successes,
                         counts=counts))
    return {'rows':rows,'circuits':circuits,'shots':shots,
            'estimated_mean_leakage':float(np.mean([v['estimated_leakage'] for v in rows])),
            'exact_mean_leakage':float(np.mean([v['exact_leakage'] for v in rows]))}
