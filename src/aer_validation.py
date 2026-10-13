"""Shot-based Qiskit Aer validation of a modeled single-qubit pulse channel.

This validates circuit/channel execution and shot statistics for the *same*
modeled channel; it is NOT an independent physical calibration or hardware test.
"""
from __future__ import annotations

import math
import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator, average_gate_fidelity
from qiskit_aer import AerSimulator

from decoherence import sequence_superop
from pulses import PAULI_X


PREPARATIONS = ("0", "1", "+", "-", "+i", "-i")


def _preparation(label: str) -> QuantumCircuit:
    qc = QuantumCircuit(1)
    if label == "0":
        pass
    elif label == "1":
        qc.x(0)
    elif label == "+":
        qc.h(0)
    elif label == "-":
        qc.x(0)
        qc.h(0)
    elif label == "+i":
        qc.h(0)
        qc.s(0)
    elif label == "-i":
        qc.h(0)
        qc.sdg(0)
    else:
        raise ValueError(f"Unknown preparation label: {label}")
    return qc


def estimate_gate_fidelity(
    sequence: str, *, amplitude_error: float, detuning_rad_per_ns: float,
    primitive_duration_ns: float, t1_ns: float, t2_ns: float,
    shots_per_state: int = 1024, seed: int = 2026,
) -> dict:
    """Estimate average X-gate fidelity from six input-state survival circuits.

    Six Pauli-axis cardinal states form a single-qubit state 2-design. For each
    one, prepare |psi>, apply the modeled noisy operation, then undo the ideal
    X and preparation before measuring the zero outcome. Their mean estimates
    average gate fidelity, with finite-shot statistical uncertainty.
    """
    if isinstance(shots_per_state, bool) or not isinstance(shots_per_state, int) or not 32 <= shots_per_state <= 100_000:
        raise ValueError("shots_per_state must be an integer from 32 to 100000")
    if not isinstance(seed, int) or isinstance(seed, bool):
        raise ValueError("seed must be an integer")
    if not np.isfinite(primitive_duration_ns) or primitive_duration_ns <= 0:
        raise ValueError("primitive_duration_ns must be positive and finite")
    omega = np.pi / primitive_duration_ns
    channel = sequence_superop(
        sequence, omega, amplitude_error=amplitude_error,
        detuning_rad_per_ns=detuning_rad_per_ns,
        t1_ns=t1_ns, t2_ns=t2_ns,
    )
    if not channel.is_cptp():
        raise ValueError("Computed quantum channel is not CPTP")
    instruction = channel.to_instruction()  # Kraus or unitary instruction
    circuits = []
    for label in PREPARATIONS:
        prep = _preparation(label)
        qc = QuantumCircuit(1, 1)
        qc.compose(prep, inplace=True)
        qc.append(instruction, [0])
        qc.x(0)  # Undo the ideal X target
        qc.compose(prep.inverse(), inplace=True)
        qc.measure(0, 0)
        circuits.append(qc)
    result = AerSimulator(method="density_matrix").run(
        circuits, shots=shots_per_state, seed_simulator=seed
    ).result()
    observations = []
    for i, label in enumerate(PREPARATIONS):
        counts = result.get_counts(i)
        p_zero = counts.get("0", 0) / shots_per_state
        observations.append({"state": label, "p_ideal_output": p_zero,
                             "successes": int(counts.get("0", 0))})
    probabilities = [row["p_ideal_output"] for row in observations]
    estimate = float(np.mean(probabilities))
    standard_error = math.sqrt(sum(p * (1 - p) / shots_per_state
                                   for p in probabilities)) / len(probabilities)
    predicted = float(average_gate_fidelity(channel, target=Operator(PAULI_X)))
    return {
        "sequence": sequence,
        "predicted_fidelity": predicted,
        "shot_estimated_fidelity": estimate,
        "shot_standard_error": standard_error,
        "shots_per_state": shots_per_state,
        "total_shots": shots_per_state * len(PREPARATIONS),
        "per_state": observations,
        "circuits": circuits,
    }
