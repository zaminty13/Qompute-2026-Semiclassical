"""Qiskit circuit validations for synthesized controls, using the same model.

Qiskit Aer shot checks are *not* independent hardware validation.
"""
from __future__ import annotations
import numpy as np
from research_synthesis import X, channel, fidelity_from_superop

LABELS=('0','1','+','-','+i','-i')


def _prepare(label):
    from qiskit import QuantumCircuit
    qc=QuantumCircuit(1)
    if label=='0': pass
    elif label=='1': qc.x(0)
    elif label=='+': qc.h(0)
    elif label=='-': qc.x(0); qc.h(0)
    elif label=='+i': qc.h(0); qc.s(0)
    elif label=='-i': qc.h(0); qc.sdg(0)
    else: raise ValueError('Unknown input state')
    return qc


def six_state_aer_check(segments, ex, *, shots=1024,seed=2026):
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import SuperOp, Operator, average_gate_fidelity
    from qiskit_aer import AerSimulator
    if not isinstance(shots,int) or isinstance(shots,bool) or not 64<=shots<=100000:
        raise ValueError('shots out of range')
    model_s=channel(segments,ex,ex.amplitude_center,ex.detuning_center_over_omega)
    s=SuperOp(model_s)
    if not s.is_cptp():
        raise ValueError('Derived noise channel is not CPTP')
    instruction=s.to_instruction()
    circuits=[]
    for label in LABELS:
        prep=_prepare(label)
        qc=QuantumCircuit(1,1)
        qc.compose(prep,inplace=True)
        qc.append(instruction,[0])
        qc.x(0)
        qc.compose(prep.inverse(),inplace=True)
        qc.measure(0,0)
        circuits.append(qc)
    sim=AerSimulator(method='density_matrix')
    rr=sim.run(circuits,shots=shots,seed_simulator=seed).result()
    successes=np.array([rr.get_counts(i).get('0',0) for i in range(len(LABELS))])
    p=successes/shots
    observed=float(p.mean())
    se=float(np.sqrt(np.sum(p*(1-p)/shots))/len(LABELS))
    predicted=float(average_gate_fidelity(s,target=Operator(X)))
    local_formula=fidelity_from_superop(model_s)
    return {'predicted_fidelity':predicted,
            'analytical_vs_qiskit_error':abs(predicted-local_formula),
            'shot_estimate':observed,'shot_standard_error':se,
            'shots_per_state':shots,'total_shots':shots*len(LABELS),
            'states':list(LABELS),'counts':successes.tolist(),
            'circuits':circuits}
