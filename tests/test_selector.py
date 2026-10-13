"""Regression tests for PulseWise selector, to run from repository root."""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from select_pulse import evaluate_pulses, select_pulse, robust_select_pulse


class SelectorTests(unittest.TestCase):
    def test_ideal_sequence(self):
        choice, rows = select_pulse(min_fidelity=1.0, amplitude_error=0.,
                                    detuning_rad_per_ns=0., t1_ns=np.inf, t2_ns=np.inf)
        self.assertEqual(choice['sequence'], 'primitive')
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertAlmostEqual(row['fidelity'], 1., places=12)

    def test_total_duration_ratios(self):
        rows = evaluate_pulses()
        durations = {r['sequence']: r['duration_ns'] for r in rows}
        self.assertAlmostEqual(durations['primitive'], 100.)
        self.assertAlmostEqual(durations['BB1'], 500.)
        self.assertAlmostEqual(durations['CORPSE'], 100. * 13 / 3)

    def test_decoherence_limited_prefers_primitive(self):
        choice, rows = select_pulse(min_fidelity=.99, amplitude_error=.05,
                                    detuning_rad_per_ns=0., primitive_duration_ns=100.,
                                    t1_ns=30000., t2_ns=20000.)
        self.assertEqual(choice['sequence'], 'primitive')
        self.assertAlmostEqual(choice['fidelity'], .9936959300972285, places=9)

    def test_amplitude_error_prefers_bb1(self):
        choice, _ = select_pulse(min_fidelity=.997, amplitude_error=.05,
                                 detuning_rad_per_ns=0., primitive_duration_ns=100.,
                                 t1_ns=200000., t2_ns=150000.)
        self.assertEqual(choice['sequence'], 'BB1')
        self.assertAlmostEqual(choice['fidelity'], .99847446, places=7)

    def test_detuning_error_prefers_corpse(self):
        choice, _ = select_pulse(min_fidelity=.997, amplitude_error=0.,
                                 detuning_rad_per_ns=np.pi / 100 * .1,
                                 primitive_duration_ns=100., t1_ns=200000., t2_ns=150000.)
        self.assertEqual(choice['sequence'], 'CORPSE')
        self.assertAlmostEqual(choice['fidelity'], .99867079, places=7)

    def test_no_feasible_result_is_explicit(self):
        choice, rows = select_pulse(min_fidelity=1.0, amplitude_error=.05,
                                    t1_ns=30000., t2_ns=20000.)
        self.assertIsNone(choice)
        self.assertEqual(len(rows), 3)

    def test_robust_selector_and_wide_uncertainty(self):
        choice, rows = robust_select_pulse()
        self.assertEqual(choice['sequence'], 'BB1')
        self.assertEqual(len(rows), 3)
        self.assertAlmostEqual(choice['sampled_worst_fidelity'], .9982016, places=6)
        no_choice, _ = robust_select_pulse(detuning_uncertainty_over_omega=.05)
        self.assertIsNone(no_choice)

    def test_invalid_parameters(self):
        for limit in [-.01, 1.01, np.nan, np.inf]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                select_pulse(min_fidelity=limit)
        for points in [0, 2, 3.0, True]:
            with self.subTest(points=points), self.assertRaises(ValueError):
                robust_select_pulse(points_per_axis=points)
        for params in [dict(amplitude_uncertainty=-1),
                       dict(detuning_uncertainty_over_omega=np.nan),
                       dict(primitive_duration_ns=0)]:
            with self.subTest(params=params), self.assertRaises(ValueError):
                robust_select_pulse(**params)


if __name__ == '__main__':
    unittest.main()
