import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.linalg import expm
from qiskit.quantum_info import Operator, average_gate_fidelity

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import pulses as p

OMEGA = np.pi / 100


def reference_segments(name):
    phi = np.arccos(-1 / 4)
    return {'primitive': [(180, 0)],
            'BB1': [(180, 0), (180, phi), (360, 3 * phi), (180, phi)],
            'CORPSE': [(420, 0), (300, np.pi), (60, 0)]}[name]


def reference_sequence(name, epsilon, delta, reverse=False):
    result = np.eye(2, dtype=complex)
    segments = reference_segments(name)
    if reverse:
        segments = segments[::-1]
    for degrees, phase in segments:
        hamiltonian = (OMEGA * (1 + epsilon) * (np.cos(phase) * p.PAULI_X
                       + np.sin(phase) * p.PAULI_Y) + delta * p.PAULI_Z) / 2
        result = expm(-1j * hamiltonian * np.deg2rad(degrees) / OMEGA) @ result
    return result


class PulseTests(unittest.TestCase):
    def test_segment_definitions_and_equal_drive_durations(self):
        for name, multiplier in zip(p.SEQUENCE_NAMES, [1, 5, 13 / 3]):
            with self.subTest(sequence=name):
                expected = [(np.deg2rad(angle), phase) for angle, phase in reference_segments(name)]
                np.testing.assert_allclose(p.sequence_segments(name), expected, atol=1e-14, rtol=0)
                for omega in [OMEGA, 2 * OMEGA]:
                    self.assertAlmostEqual(p.sequence_duration_ns(name, omega), multiplier * np.pi / omega, places=11)

    def test_ideal_x_global_phase_and_fidelity(self):
        for name in p.SEQUENCE_NAMES:
            for omega in [OMEGA / 2, OMEGA, OMEGA * 2]:
                with self.subTest(sequence=name, omega=omega):
                    result = p.simulate_sequence(name, omega)
                    self.assertTrue(result.operation.equiv(Operator(p.PAULI_X)))
                    self.assertAlmostEqual(result.average_gate_fidelity, 1, places=14)
                    self.assertLess(result.average_gate_infidelity, 1e-28)
                    self.assertEqual(result.sequence, name)
                    self.assertEqual(result.total_duration_ns, p.sequence_duration_ns(name, omega))

    def test_unitarity_and_independent_dynamics(self):
        for name in p.SEQUENCE_NAMES:
            for epsilon in [-1, -.2, 0, .15]:
                for detuning in [-.5, 0, .3]:
                    with self.subTest(sequence=name, epsilon=epsilon, detuning=detuning):
                        actual = p.sequence_unitary(name, OMEGA, epsilon, detuning * OMEGA)
                        np.testing.assert_allclose(actual.conj().T @ actual, p.IDENTITY, atol=5e-14, rtol=0)
                        np.testing.assert_allclose(actual, reference_sequence(name, epsilon, detuning * OMEGA), atol=5e-14, rtol=0)
                        expected = average_gate_fidelity(Operator(actual), target=Operator(p.PAULI_X))
                        self.assertAlmostEqual(p.average_fidelity(actual, p.PAULI_X), expected, places=13)

    def test_chronological_order_is_observable(self):
        for name in ['BB1', 'CORPSE']:
            actual = p.sequence_unitary(name, OMEGA, .12, .17 * OMEGA)
            np.testing.assert_allclose(actual, reference_sequence(name, .12, .17 * OMEGA), atol=5e-14, rtol=0)
            self.assertGreater(np.linalg.norm(actual - reference_sequence(name, .12, .17 * OMEGA, reverse=True)), 1e-3)

    def test_primitive_analytic_amplitude_and_small_error(self):
        errors = np.linspace(-.2, .2, 401)
        for duration in [20, 50, 100, 200]:
            actual = p.average_infidelity(p.x_pulse_unitary(duration, errors), p.PAULI_X)
            np.testing.assert_allclose(actual, p.analytic_x_infidelity(errors), atol=2e-15, rtol=0)
        for error in [1e-4, 1e-8, 1e-12]:
            actual = p.average_infidelity(p.x_pulse_unitary(100, error), p.PAULI_X)
            self.assertGreater(actual, 0)
            self.assertAlmostEqual(actual / p.small_error_infidelity(error), 1, delta=max(1e-8, 8 * np.finfo(float).eps / error))
        p.cross_check(Operator(p.PAULI_X), [20, 100], errors)

    def test_primitive_analytic_detuning(self):
        f = np.linspace(-1, 1, 201)
        a = np.pi / 2 * np.sqrt(1 + f * f)
        expected = 2 / 3 * (np.cos(a)**2 + f*f / (1 + f*f) * np.sin(a)**2)
        actual = p.average_infidelity(p.x_pulse_unitary(100, detuning_rad_per_ns=f * OMEGA), p.PAULI_X)
        np.testing.assert_allclose(actual, expected, atol=2e-15, rtol=0)
        small = 1e-4
        value = p.average_infidelity(p.x_pulse_unitary(100, detuning_rad_per_ns=small * OMEGA), p.PAULI_X)
        self.assertAlmostEqual(value / small**2, 2 / 3, delta=1e-8)

    def test_expected_error_scaling(self):
        for name, mode, power in [('primitive', 'amplitude', 2), ('BB1', 'amplitude', 6),
                                   ('primitive', 'detuning', 2), ('CORPSE', 'detuning', 4)]:
            values = []
            scale = .001 if name == 'CORPSE' else .01
            for error in [scale, scale / 2]:
                kwargs = {'amplitude_error': error} if mode == 'amplitude' else {'detuning_rad_per_ns': error * OMEGA}
                values.append(p.average_infidelity(p.sequence_unitary(name, OMEGA, **kwargs), p.PAULI_X))
            self.assertAlmostEqual(np.log2(values[0] / values[1]), power, delta=.03)
        for mode, name in [('amplitude', 'BB1'), ('detuning', 'CORPSE')]:
            kwargs = {'amplitude_error': .01} if mode == 'amplitude' else {'detuning_rad_per_ns': .01 * OMEGA}
            primitive = p.average_infidelity(p.sequence_unitary('primitive', OMEGA, **kwargs), p.PAULI_X)
            composite = p.average_infidelity(p.sequence_unitary(name, OMEGA, **kwargs), p.PAULI_X)
            self.assertLess(composite, primitive / 1000)

    def test_corpse_leading_detuning_coefficient(self):
        f = 1e-4
        actual = p.average_infidelity(p.sequence_unitary('CORPSE', OMEGA,
                                     detuning_rad_per_ns=f * OMEGA), p.PAULI_X)
        coefficient = (np.pi / 2 - np.sqrt(3))**2 / 6
        self.assertAlmostEqual(actual / f**4, coefficient, delta=1e-7)

    def test_no_universal_composite_advantage(self):
        errors = np.linspace(-.3, .3, 61)
        np.testing.assert_allclose(p.average_infidelity(p.sequence_unitary('CORPSE', OMEGA, errors), p.PAULI_X),
                                   p.analytic_x_infidelity(errors), atol=3e-15, rtol=0)
        self.assertGreater(p.average_infidelity(p.sequence_unitary('CORPSE', OMEGA, detuning_rad_per_ns=OMEGA), p.PAULI_X),
                           p.average_infidelity(p.sequence_unitary('primitive', OMEGA, detuning_rad_per_ns=OMEGA), p.PAULI_X))

    def test_bb1_signed_detuning_and_small_amplitude_coefficient(self):
        negative = p.average_infidelity(p.sequence_unitary('BB1', OMEGA,
                                        detuning_rad_per_ns=-.5 * OMEGA), p.PAULI_X)
        positive = p.average_infidelity(p.sequence_unitary('BB1', OMEGA,
                                        detuning_rad_per_ns=.5 * OMEGA), p.PAULI_X)
        primitive = p.average_infidelity(p.sequence_unitary('primitive', OMEGA,
                                         detuning_rad_per_ns=-.5 * OMEGA), p.PAULI_X)
        self.assertGreater(negative, primitive)
        self.assertLess(positive, primitive)
        epsilon = .01
        actual = p.average_infidelity(p.sequence_unitary('BB1', OMEGA, epsilon), p.PAULI_X)
        self.assertAlmostEqual(actual / epsilon**6, 5 * np.pi**6 / 768, delta=.002)

    def test_broadcasting(self):
        eps = np.array([-.1, 0, .1])[:, None]
        delta = np.array([-.2, 0, .2, .3])[None, :] * OMEGA
        for name in p.SEQUENCE_NAMES:
            actual = p.sequence_unitary(name, OMEGA, eps, delta)
            self.assertEqual(actual.shape, (3, 4, 2, 2))
            for i in range(3):
                for j in range(4):
                    np.testing.assert_allclose(actual[i, j], reference_sequence(name, eps[i, 0], delta[0, j]), atol=5e-14, rtol=0)

    def test_zero_drive_and_detuning_sign(self):
        np.testing.assert_array_equal(p.pulse_unitary(100, 0), p.IDENTITY)
        np.testing.assert_array_equal(p.pulse_unitary(100, OMEGA, amplitude_error=-1), p.IDENTITY)
        expected = np.diag([np.exp(-.5j), np.exp(.5j)])
        np.testing.assert_allclose(p.pulse_unitary(100, 0, detuning_rad_per_ns=.01), expected, atol=1e-15)
        np.testing.assert_allclose(p.pulse_unitary(100, OMEGA, amplitude_error=-1, detuning_rad_per_ns=.01), expected, atol=1e-15)

    def test_invalid_inputs(self):
        for duration in [0, -1, np.nan, np.inf, [100], 1j, '100']:
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                p.x_pulse_unitary(duration)
        for name in ['omega_rad_per_ns', 'phase_rad', 'amplitude_error', 'detuning_rad_per_ns']:
            for value in [np.nan, np.inf, 1j, 'bad']:
                kwargs = dict(duration_ns=100, omega_rad_per_ns=OMEGA)
                kwargs[name] = value
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    p.pulse_unitary(**kwargs)
        for omega in [0, -1, np.inf, [OMEGA]]:
            with self.assertRaises(ValueError):
                p.sequence_unitary('BB1', omega)
        with self.assertRaises(ValueError):
            p.sequence_unitary('unknown', OMEGA)
        with self.assertRaises(ValueError):
            p.pulse_unitary(1e308, 1e308)
        with self.assertRaises(ValueError):
            p.pulse_unitary(100, OMEGA, amplitude_error=np.zeros(3), detuning_rad_per_ns=np.zeros(2))
        for call in [p.basic_x_pulse, lambda amplitude_error: p.simulate_sequence('BB1', OMEGA, amplitude_error)]:
            with self.assertRaises(ValueError):
                call(amplitude_error=[0, .1])
        for matrix in [np.zeros((2, 2)), np.eye(3), np.full((2, 2), np.nan)]:
            with self.assertRaises(ValueError):
                p.average_fidelity(matrix, p.PAULI_X)

    def test_comparison_rejects_invalid_data(self):
        for actual, expected in [([np.nan], [0]), ([0], [np.inf]), ([], []), ([0, 0], [0])]:
            with self.assertRaises(ValueError):
                p.require_close('test', actual, expected)
        with self.assertRaises(RuntimeError):
            p.require_close('test', [0], [1])
        with self.assertRaises(ValueError):
            p.cross_check(Operator(p.PAULI_X), [100], [np.nan])


if __name__ == '__main__':
    unittest.main()
