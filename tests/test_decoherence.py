import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp
from qiskit.quantum_info import Choi, DensityMatrix, Operator, SuperOp

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import decoherence as d
import pulses as p

OMEGA = np.pi / 100


class DecoherenceTests(unittest.TestCase):
    def test_zero_decoherence_matches_coherent_sequences(self):
        for name in p.SEQUENCE_NAMES:
            for epsilon, delta in [(0, 0), (.12, -.17 * OMEGA), (-1, .3 * OMEGA)]:
                with self.subTest(sequence=name, epsilon=epsilon, delta=delta):
                    actual = d.sequence_superop(name, OMEGA, epsilon, delta)
                    self.assertIsInstance(actual, SuperOp)
                    expected = SuperOp(Operator(p.sequence_unitary(name, OMEGA, epsilon, delta)))
                    np.testing.assert_allclose(actual.data, expected.data, atol=1e-13, rtol=0)
        self.assertIsInstance(p.simulate_sequence('primitive', OMEGA).operation, Operator)

    def test_idle_relaxation_and_total_coherence_decay(self):
        for t1, t2 in [(200, 400), (200, 75), (np.inf, 75)]:
            for time in [1, 100, 500]:
                delta = .013
                survival = np.exp(-time / t1)
                coherence = np.exp(-time / t2 - 1j * delta * time)
                expected = np.array([[1, 0, 0, 1 - survival],
                                     [0, coherence.conjugate(), 0, 0],
                                     [0, 0, coherence, 0],
                                     [0, 0, 0, survival]])
                actual = d.pulse_superop(time, 0, detuning_rad_per_ns=delta,
                                         t1_ns=t1, t2_ns=t2)
                np.testing.assert_allclose(actual.data, expected, atol=2e-14, rtol=0)
                ground = DensityMatrix.from_label('0').evolve(actual)
                np.testing.assert_allclose(ground.data, np.diag([1, 0]), atol=1e-14)

    def test_noise_covers_total_composite_duration(self):
        for name, multiplier in zip(p.SEQUENCE_NAMES, [1, 5, 13 / 3]):
            channel = d.sequence_superop(name, OMEGA, amplitude_error=-1,
                                         t1_ns=200, t2_ns=120)
            duration = 100 * multiplier
            excited = DensityMatrix.from_label('1').evolve(channel)
            self.assertAlmostEqual(excited.data[1, 1].real, np.exp(-duration / 200), places=13)
            plus = DensityMatrix.from_label('+').evolve(channel)
            self.assertAlmostEqual(plus.data[0, 1].real, .5 * np.exp(-duration / 120), places=13)

    def test_simultaneous_driven_dynamics_against_matrix_ode(self):
        phi = np.arccos(-.25)
        segments = {'primitive': [(np.pi, 0)],
                    'BB1': [(np.pi, 0), (np.pi, phi), (2 * np.pi, 3 * phi), (np.pi, phi)],
                    'CORPSE': [(7 * np.pi / 3, 0), (5 * np.pi / 3, np.pi), (np.pi / 3, 0)]}
        lower = np.array([[0, 1], [0, 0]], dtype=complex)
        excited = np.diag([0, 1])
        for name in p.SEQUENCE_NAMES:
            channel = d.sequence_superop(name, OMEGA, .12, -.17 * OMEGA,
                                         t1_ns=230, t2_ns=140)
            for label in ['0', '1', '+', 'r']:
                initial = DensityMatrix.from_label(label)
                rho = initial.data.copy()
                for angle, phase in segments[name]:
                    h = (OMEGA * 1.12 * (np.cos(phase) * p.PAULI_X
                                         + np.sin(phase) * p.PAULI_Y)
                         - .17 * OMEGA * p.PAULI_Z) / 2

                    def rhs(t, flat):
                        state = flat.reshape(2, 2)
                        derivative = -1j * (h @ state - state @ h)
                        derivative += (lower @ state @ lower.conj().T
                                       - .5 * (excited @ state + state @ excited)) / 230
                        derivative += (1 / 140 - 1 / 460) / 2 * (p.PAULI_Z @ state @ p.PAULI_Z - state)
                        return derivative.ravel()

                    solution = solve_ivp(rhs, (0, angle / OMEGA), rho.ravel(),
                                         rtol=1e-11, atol=1e-13)
                    self.assertTrue(solution.success)
                    rho = solution.y[:, -1].reshape(2, 2)
                np.testing.assert_allclose(initial.evolve(channel).data, rho, atol=2e-11, rtol=0)

    def test_completely_positive_trace_preserving_channels(self):
        for name in p.SEQUENCE_NAMES:
            for t1, t2 in [(np.inf, np.inf), (np.inf, 100), (200, 400), (200, 70), (1, 1)]:
                channel = d.sequence_superop(name, OMEGA, .13, -.21 * OMEGA,
                                             t1_ns=t1, t2_ns=t2)
                with self.subTest(sequence=name, t1=t1, t2=t2):
                    self.assertTrue(channel.is_cptp(atol=1e-12, rtol=0))
                    choi = Choi(channel).data
                    np.testing.assert_allclose(choi, choi.conj().T, atol=1e-13, rtol=0)
                    self.assertGreaterEqual(np.linalg.eigvalsh(choi).min(), -1e-12)
                    trace = np.array([1, 0, 0, 1])
                    np.testing.assert_allclose(trace @ channel.data, trace, atol=1e-12, rtol=0)

    def test_invalid_coherence_times(self):
        for key in ['t1_ns', 't2_ns']:
            for value in [0, -1, -np.inf, np.nan, 1j, '100', [100], True]:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    d.sequence_superop('primitive', OMEGA, **{key: value})
        for t1, t2 in [(100, 201), (100, np.inf)]:
            with self.assertRaises(ValueError):
                d.sequence_superop('primitive', OMEGA, t1_ns=t1, t2_ns=t2)

    def test_invalid_pulse_parameters(self):
        for key in ['duration_ns', 'omega_rad_per_ns', 'phase_rad',
                    'amplitude_error', 'detuning_rad_per_ns']:
            for value in [np.nan, np.inf, [1], 1j, 'bad']:
                kwargs = dict(duration_ns=100, omega_rad_per_ns=OMEGA)
                kwargs[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    d.pulse_superop(**kwargs)
        for duration in [0, -1]:
            with self.assertRaises(ValueError):
                d.pulse_superop(duration, OMEGA)
        for omega in [0, -1]:
            with self.assertRaises(ValueError):
                d.sequence_superop('primitive', omega)
        with self.assertRaises(ValueError):
            d.sequence_superop('unknown', OMEGA)


if __name__ == '__main__':
    unittest.main()
