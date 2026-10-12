from dataclasses import dataclass

import numpy as np
from qiskit.circuit.library import XGate
from qiskit.quantum_info import Operator, average_gate_fidelity

PAULI_X = np.array([[0, 1], [1, 0]], dtype=complex)
PAULI_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
PAULI_Z = np.diag([1, -1]).astype(complex)
IDENTITY = np.eye(2, dtype=complex)


def _require_finite(**values):
    bad = []
    for name, value in values.items():
        array = np.asarray(value)
        if array.dtype.kind not in "iuf" or not np.all(np.isfinite(array)):
            bad.append(name)
    if bad:
        raise ValueError(f"Expected finite real numeric values for: {', '.join(bad)}.")


def _require_scalars(**values):
    arrays = [name for name, value in values.items() if np.ndim(value)]
    if arrays:
        raise ValueError(f"Expected a scalar for: {', '.join(arrays)}.")


def _require_positive_duration(duration_ns):
    _require_finite(duration_ns=duration_ns)
    _require_scalars(duration_ns=duration_ns)
    if duration_ns <= 0:
        raise ValueError("duration_ns must be positive.")


def pulse_unitary(
    duration_ns,
    omega_rad_per_ns,
    phase_rad=0.0,
    amplitude_error=0.0,
    detuning_rad_per_ns=0.0,
):
    _require_finite(omega_rad_per_ns=omega_rad_per_ns, phase_rad=phase_rad,
                    amplitude_error=amplitude_error,
                    detuning_rad_per_ns=detuning_rad_per_ns)
    _require_scalars(omega_rad_per_ns=omega_rad_per_ns, phase_rad=phase_rad)
    _require_positive_duration(duration_ns)
    epsilon, delta = np.broadcast_arrays(np.asarray(amplitude_error, dtype=float),
                                         np.asarray(detuning_rad_per_ns, dtype=float))
    with np.errstate(over="ignore", invalid="ignore"):
        transverse = omega_rad_per_ns * (1 + epsilon) * (duration_ns / 2)
        longitudinal = delta * (duration_ns / 2)
        radius = np.hypot(transverse, longitudinal)
    _require_finite(transverse=transverse, longitudinal=longitudinal, radius=radius)
    axis = np.cos(phase_rad) * PAULI_X + np.sin(phase_rad) * PAULI_Y
    generator = transverse[..., None, None] * axis + longitudinal[..., None, None] * PAULI_Z
    return (np.cos(radius)[..., None, None] * IDENTITY
            - 1j * np.sinc(radius / np.pi)[..., None, None] * generator)


def x_pulse_unitary(duration_ns=100.0, amplitude_error=0.0, detuning_rad_per_ns=0.0):
    _require_positive_duration(duration_ns)
    return pulse_unitary(duration_ns, np.pi / duration_ns, 0.0,
                         amplitude_error, detuning_rad_per_ns)


def rectangular_pulse(duration_ns, omega_rad_per_ns, phase_rad=0.0,
                      amplitude_error=0.0, detuning_rad_per_ns=0.0):
    _require_scalars(amplitude_error=amplitude_error, detuning_rad_per_ns=detuning_rad_per_ns)
    return Operator(pulse_unitary(duration_ns, omega_rad_per_ns, phase_rad,
                                  amplitude_error, detuning_rad_per_ns))


def basic_x_pulse(duration_ns=100.0, amplitude_error=0.0, detuning_rad_per_ns=0.0):
    _require_scalars(amplitude_error=amplitude_error, detuning_rad_per_ns=detuning_rad_per_ns)
    return Operator(x_pulse_unitary(duration_ns, amplitude_error, detuning_rad_per_ns))


def _validated_unitary(value, name):
    value = np.asarray(value, dtype=complex)
    if value.shape[-2:] != (2, 2) or not np.all(np.isfinite(value)):
        raise ValueError(f"{name} must contain finite 2x2 unitaries.")
    if not np.allclose(value.conj().swapaxes(-1, -2) @ value, IDENTITY,
                       atol=1e-10, rtol=0):
        raise ValueError(f"{name} must be unitary; use channel fidelity for decoherence.")
    return value


def average_infidelity(unitary, target):
    unitary = _validated_unitary(unitary, "unitary")
    target = _validated_unitary(target, "target")
    relative = target.conj().swapaxes(-1, -2) @ unitary
    trace = np.trace(relative, axis1=-2, axis2=-1)
    residual = relative - (trace / 2)[..., None, None] * IDENTITY
    return np.sum(np.abs(residual) ** 2, axis=(-2, -1)) / 3


def average_fidelity(unitary, target):
    return 1.0 - average_infidelity(unitary, target)


def analytic_x_infidelity(amplitude_error):
    _require_finite(amplitude_error=amplitude_error)
    return (2 / 3) * np.sin(np.pi * np.asarray(amplitude_error) / 2) ** 2


def analytic_x_fidelity(amplitude_error):
    return 1.0 - analytic_x_infidelity(amplitude_error)


def small_error_infidelity(amplitude_error):
    _require_finite(amplitude_error=amplitude_error)
    return (np.pi * np.asarray(amplitude_error)) ** 2 / 6


def require_close(name, actual, expected, atol=1e-12):
    actual, expected = np.asarray(actual), np.asarray(expected)
    if (actual.shape != expected.shape or actual.size == 0
            or not np.all(np.isfinite(actual)) or not np.all(np.isfinite(expected))
            or not np.isfinite(atol) or atol < 0):
        raise ValueError(f"Invalid comparison data or tolerance for {name}.")
    worst = np.max(np.abs(actual - expected))
    if worst > atol:
        raise RuntimeError(f"Disagreement with {name}: max difference {worst:.2e}.")


def cross_check(ideal_x, durations_ns, errors, atol=1e-12):
    errors = np.asarray(errors, dtype=float)
    exact = analytic_x_fidelity(errors)
    for duration_ns in durations_ns:
        fast = average_fidelity(x_pulse_unitary(duration_ns, errors), ideal_x.data)
        reference = np.array([average_gate_fidelity(basic_x_pulse(duration_ns, error),
                              target=ideal_x) for error in errors])
        require_close("Qiskit", fast, reference, atol)
        require_close("analytic X", reference, exact, atol)


SEQUENCE_NAMES = ("primitive", "BB1", "CORPSE")


def sequence_segments(sequence):
    if sequence == "primitive":
        return ((np.pi, 0.0),)
    if sequence == "BB1":
        phi = np.arccos(-0.25)
        return ((np.pi, 0.0), (np.pi, phi), (2 * np.pi, 3 * phi), (np.pi, phi))
    if sequence == "CORPSE":
        return ((7 * np.pi / 3, 0.0), (5 * np.pi / 3, np.pi), (np.pi / 3, 0.0))
    raise ValueError(f"Unknown sequence {sequence!r}; expected one of {SEQUENCE_NAMES}.")


def sequence_duration_ns(sequence, omega_rad_per_ns):
    _require_finite(omega_rad_per_ns=omega_rad_per_ns)
    _require_scalars(omega_rad_per_ns=omega_rad_per_ns)
    if omega_rad_per_ns <= 0:
        raise ValueError("Nominal drive strength must be positive.")
    duration = sum(angle for angle, _ in sequence_segments(sequence)) / omega_rad_per_ns
    _require_finite(duration_ns=duration)
    return duration


def sequence_unitary(sequence, omega_rad_per_ns, amplitude_error=0.0,
                     detuning_rad_per_ns=0.0):
    sequence_duration_ns(sequence, omega_rad_per_ns)
    result = IDENTITY.copy()
    for angle, phase in sequence_segments(sequence):
        result = pulse_unitary(angle / omega_rad_per_ns, omega_rad_per_ns, phase,
                               amplitude_error, detuning_rad_per_ns) @ result
    return result


@dataclass(frozen=True)
class PulseResult:
    operation: Operator
    average_gate_fidelity: float
    total_duration_ns: float
    sequence: str
    average_gate_infidelity: float


def simulate_sequence(sequence, omega_rad_per_ns, amplitude_error=0.0,
                      detuning_rad_per_ns=0.0):
    _require_scalars(amplitude_error=amplitude_error, detuning_rad_per_ns=detuning_rad_per_ns)
    unitary = sequence_unitary(sequence, omega_rad_per_ns, amplitude_error, detuning_rad_per_ns)
    infidelity = float(average_infidelity(unitary, PAULI_X))
    return PulseResult(Operator(unitary), 1 - infidelity,
                       sequence_duration_ns(sequence, omega_rad_per_ns), sequence, infidelity)


def main():
    ideal_x = Operator(XGate())
    duration_ns = 100.0
    errors = np.array([-0.10, -0.05, -0.01, 0.0, 0.01, 0.05, 0.10])

    cross_check(
        ideal_x,
        durations_ns=(20.0, 50.0, duration_ns, 200.0),
        errors=errors,
    )

    fidelities = average_fidelity(x_pulse_unitary(duration_ns, errors), ideal_x.data)
    approximations = small_error_infidelity(errors)

    print(f"Pulse duration: {duration_ns:.1f} ns")
    print("Fidelity is identical at 20, 50, 100 and 200 ns because drive strength is recalibrated.\n")
    print(f"{'error':>8} {'fidelity':>12} {'infidelity':>12} {'pi^2 e^2 / 6':>14}")

    for error, fidelity, approximation in zip(errors, fidelities, approximations):
        print(
            f"{error:>+8.0%} {fidelity:>12.6f} {1 - fidelity:>12.6f} "
            f"{approximation:>14.6f}"
        )


if __name__ == "__main__":
    main()
