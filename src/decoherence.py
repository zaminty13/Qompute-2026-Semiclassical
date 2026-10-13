
import numpy as np
from scipy.linalg import expm
from qiskit.quantum_info import SuperOp

from pulses import (
    IDENTITY, PAULI_X, PAULI_Y, PAULI_Z,
    _require_finite, _require_positive_duration, _require_scalars,
    sequence_duration_ns, sequence_segments,
)


def _decay_rates(t1_ns, t2_ns):
    for name, value in (("t1_ns", t1_ns), ("t2_ns", t2_ns)):
        _require_scalars(**{name: value})
        array = np.asarray(value)
        if array.dtype.kind not in "iuf" or np.isnan(value) or value <= 0:
            raise ValueError(f"{name} must be a positive real time or np.inf.")
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        gamma1 = float(np.divide(1.0, t1_ns))
        gamma2 = float(np.divide(1.0, t2_ns))
    _require_finite(gamma1=gamma1, gamma2=gamma2)
    if gamma2 < gamma1 / 2:
        raise ValueError("Physical coherence times require t2_ns <= 2 * t1_ns.")
    return gamma1, gamma2 - gamma1 / 2


def pulse_superop(duration_ns, omega_rad_per_ns, phase_rad=0.0,
                  amplitude_error=0.0, detuning_rad_per_ns=0.0, *,
                  t1_ns=np.inf, t2_ns=np.inf):
    values = dict(omega_rad_per_ns=omega_rad_per_ns, phase_rad=phase_rad,
                  amplitude_error=amplitude_error,
                  detuning_rad_per_ns=detuning_rad_per_ns)
    _require_scalars(**values)
    _require_finite(**values)
    _require_positive_duration(duration_ns)
    gamma1, gamma_phi = _decay_rates(t1_ns, t2_ns)
    with np.errstate(over="ignore", invalid="ignore"):
        transverse = omega_rad_per_ns * (1 + amplitude_error)
    _require_finite(transverse=transverse)
    hamiltonian = (transverse * (np.cos(phase_rad) * PAULI_X
                                 + np.sin(phase_rad) * PAULI_Y)
                   + detuning_rad_per_ns * PAULI_Z) / 2
    generator = -1j * (np.kron(IDENTITY, hamiltonian)
                       - np.kron(hamiltonian.T, IDENTITY))
    lowering = np.array([[0, 1], [0, 0]], dtype=complex)
    for rate, jump in ((gamma1, lowering), (gamma_phi / 2, PAULI_Z)):
        product = jump.conj().T @ jump
        generator += rate * (np.kron(jump.conj(), jump)
                             - .5 * np.kron(IDENTITY, product)
                             - .5 * np.kron(product.T, IDENTITY))
    with np.errstate(over="ignore", invalid="ignore"):
        exponent = duration_ns * generator
    if not np.all(np.isfinite(exponent)):
        raise ValueError("Duration and rates produce a nonfinite Lindblad exponent.")
    return SuperOp(expm(exponent))


def sequence_superop(sequence, omega_rad_per_ns, amplitude_error=0.0,
                     detuning_rad_per_ns=0.0, *, t1_ns=np.inf, t2_ns=np.inf):
    sequence_duration_ns(sequence, omega_rad_per_ns)
    result = np.eye(4, dtype=complex)
    for angle, phase in sequence_segments(sequence):
        segment = pulse_superop(angle / omega_rad_per_ns, omega_rad_per_ns,
                                phase, amplitude_error, detuning_rad_per_ns,
                                t1_ns=t1_ns, t2_ns=t2_ns)
        result = segment.data @ result
    return SuperOp(result)
