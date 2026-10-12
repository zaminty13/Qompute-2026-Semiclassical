import numpy as np
from qiskit.circuit.library import XGate
from qiskit.quantum_info import Operator, average_gate_fidelity

PAULI_X = np.array([[0, 1], [1, 0]], dtype=complex)
PAULI_Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
IDENTITY = np.eye(2, dtype=complex)


def _require_finite(**values):
    bad = [name for name, value in values.items() if not np.all(np.isfinite(value))]
    if bad:
        raise ValueError(f"Non-finite value for: {', '.join(bad)}.")


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
):
    _require_finite(
        omega_rad_per_ns=omega_rad_per_ns,
        phase_rad=phase_rad,
        amplitude_error=amplitude_error,
    )
    _require_scalars(omega_rad_per_ns=omega_rad_per_ns, phase_rad=phase_rad)
    _require_positive_duration(duration_ns)

    angle = omega_rad_per_ns * (1 + np.asarray(amplitude_error, dtype=float)) * duration_ns
    half_angle = (angle / 2)[..., None, None]
    axis = np.cos(phase_rad) * PAULI_X + np.sin(phase_rad) * PAULI_Y

    return np.cos(half_angle) * IDENTITY - 1j * np.sin(half_angle) * axis


def x_pulse_unitary(duration_ns=100.0, amplitude_error=0.0):
    _require_positive_duration(duration_ns)

    return pulse_unitary(
        duration_ns=duration_ns,
        omega_rad_per_ns=np.pi / duration_ns,
        phase_rad=0.0,
        amplitude_error=amplitude_error,
    )


def rectangular_pulse(
    duration_ns,
    omega_rad_per_ns,
    phase_rad=0.0,
    amplitude_error=0.0,
):
    _require_scalars(amplitude_error=amplitude_error)

    return Operator(
        pulse_unitary(duration_ns, omega_rad_per_ns, phase_rad, amplitude_error)
    )


def basic_x_pulse(duration_ns=100.0, amplitude_error=0.0):
    _require_scalars(amplitude_error=amplitude_error)

    return Operator(x_pulse_unitary(duration_ns, amplitude_error))


def average_fidelity(unitary, target):
    overlap = np.abs(np.einsum("ij,...ij->...", np.conj(target), unitary)) ** 2
    return (overlap + 2) / 6


def analytic_x_fidelity(amplitude_error):
    return (1 + 2 * np.cos(np.pi * np.asarray(amplitude_error) / 2) ** 2) / 3


def small_error_infidelity(amplitude_error):
    return (np.pi * np.asarray(amplitude_error)) ** 2 / 6


def cross_check(ideal_x, durations_ns, errors, atol=1e-12):
    target = ideal_x.data
    errors = np.asarray(errors, dtype=float)
    exact = analytic_x_fidelity(errors)

    for duration_ns in durations_ns:
        fast = average_fidelity(x_pulse_unitary(duration_ns, errors), target)
        reference = np.array([
            average_gate_fidelity(basic_x_pulse(duration_ns, error), target=ideal_x)
            for error in errors
        ])
        vs_fast = np.max(np.abs(reference - fast))
        vs_exact = np.max(np.abs(reference - exact))
        if max(vs_fast, vs_exact) > atol:
            raise RuntimeError(
                f"Fidelity mismatch at {duration_ns} ns: "
                f"max |qiskit - fast| = {vs_fast:.2e}, "
                f"max |qiskit - analytic| = {vs_exact:.2e}"
            )


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