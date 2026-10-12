import csv
import sys
import tempfile
import unittest
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from qiskit.quantum_info import Operator, average_gate_fidelity

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import compare_pulses as c
import decoherence as d
import pulses as p


class ComparisonTests(unittest.TestCase):
    def test_amplitude_comparison_analytic_and_shared_drive(self):
        rows = c.amplitude_rows([-.1, 0, .1], 80)
        self.assertEqual(len(rows), 9)
        for row in rows:
            self.assertEqual(row['model'], 'coherent')
            self.assertEqual(row['detuning_rad_per_ns'], 0)
            self.assertEqual(row['t1_ns'], np.inf)
            self.assertAlmostEqual(row['omega_rad_per_ns'], np.pi / 80)
            if row['sequence'] != 'BB1':
                self.assertAlmostEqual(row['average_gate_infidelity'],
                                       p.analytic_x_infidelity(row['amplitude_error']), places=14)
        by_sequence = {r['sequence']: r['average_gate_infidelity'] for r in rows if r['amplitude_error'] == .1}
        self.assertLess(by_sequence['BB1'], by_sequence['primitive'] / 100)

    def test_duration_accounting_and_fixed_parameters(self):
        rows = c.comparison_rows([20, 100, 300], amplitude_error=.07,
                                  detuning_rad_per_ns=-.004, t1_ns=700, t2_ns=900)
        self.assertEqual(len(rows), 54)
        ratios = dict(zip(p.SEQUENCE_NAMES, [1, 5, 13 / 3]))
        for row in rows:
            self.assertAlmostEqual(row['total_duration_ns'],
                                   ratios[row['sequence']] * row['primitive_duration_ns'])
            self.assertAlmostEqual(row['omega_rad_per_ns'] * row['primitive_duration_ns'], np.pi)
            self.assertEqual(row['amplitude_error'], .07 if row['case'] == 'amplitude_only' else 0.)
            self.assertEqual(row['detuning_rad_per_ns'], -.004 if row['case'] == 'detuning_only' else 0.)
            self.assertEqual(row['t1_ns'], 700 if row['model'] == 'lindblad' else np.inf)
            self.assertEqual(row['t2_ns'], 900 if row['model'] == 'lindblad' else np.inf)

    def test_reported_fidelity_uses_complete_channel_and_common_target(self):
        rows = c.comparison_rows([90], amplitude_error=.08, detuning_rad_per_ns=.002,
                                  t1_ns=900, t2_ns=600)
        for row in rows:
            if row['model'] == 'lindblad':
                channel = d.sequence_superop(row['sequence'], np.pi / 90,
                    row['amplitude_error'], row['detuning_rad_per_ns'], t1_ns=900, t2_ns=600)
                expected = average_gate_fidelity(channel, target=Operator(p.PAULI_X))
                self.assertAlmostEqual(row['average_gate_fidelity'], expected, places=14)
            self.assertAlmostEqual(row['average_gate_fidelity'] + row['average_gate_infidelity'], 1, places=14)

    def test_zero_noise_comparisons_and_duration_effect(self):
        rows = c.comparison_rows([30, 200], t1_ns=np.inf, t2_ns=np.inf)
        for coherent, noisy in zip(rows[::2], rows[1::2]):
            self.assertAlmostEqual(coherent['average_gate_fidelity'], noisy['average_gate_fidelity'], places=13)
        rows = c.comparison_rows([30, 200])
        for sequence in p.SEQUENCE_NAMES:
            subset = [r for r in rows if r['sequence'] == sequence and r['case'] == 'no_control_error']
            coherent = [r for r in subset if r['model'] == 'coherent']
            noisy = [r for r in subset if r['model'] == 'lindblad']
            for row in coherent:
                self.assertAlmostEqual(row['average_gate_fidelity'], 1, places=14)
            self.assertGreater(noisy[0]['average_gate_fidelity'], noisy[1]['average_gate_fidelity'])

    def test_csv_round_trip_and_row_coverage(self):
        for rows in (c.amplitude_rows([-.1, 0, .1]), c.comparison_rows([100]),
                     c.comparison_rows([20, 100, 500])):
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'nested' / 'comparison.csv'
                c.write_csv(path, rows)
                with path.open(newline='', encoding='utf-8') as stream:
                    reader = csv.DictReader(stream)
                    self.assertEqual(tuple(reader.fieldnames), c.FIELDS)
                    loaded = list(reader)
                self.assertEqual(len(loaded), len(rows))
                keys = {(r['case'], r['sequence'], r['model'], r['primitive_duration_ns'], r['amplitude_error'])
                        for r in loaded}
                self.assertEqual(len(keys), len(rows))
                for original, saved in zip(rows, loaded):
                    for key in c.FIELDS:
                        if key in ('case', 'sequence', 'model'):
                            self.assertEqual(saved[key], original[key])
                        else:
                            self.assertEqual(float(saved[key]), original[key])

    def test_plot_curve_coverage_and_duration_axes(self):
        amplitude = c.plot_amplitude(c.amplitude_rows([-.1, 0, .1]))
        self.assertEqual(len(amplitude.axes[0].lines), 3)
        plt.close(amplitude)
        rows = c.comparison_rows([20, 100, 500])
        for actual, key in ((False, 'primitive_duration_ns'), (True, 'total_duration_ns')):
            figure = c.plot_duration(rows, actual_duration=actual)
            for ax, case in zip(figure.axes, c.representative_cases()):
                self.assertEqual(len(ax.lines), 6)
                for line, (sequence, model) in zip(ax.lines,
                    [(s, m) for s in p.SEQUENCE_NAMES for m in ('coherent', 'lindblad')]):
                    expected = [r[key] for r in rows if r['case'] == case[0]
                                and r['sequence'] == sequence and r['model'] == model]
                    np.testing.assert_allclose(line.get_xdata(), expected)
                    self.assertTrue(np.all(np.isfinite(line.get_ydata())))
                    self.assertGreaterEqual(min(line.get_ydata()), ax.get_ylim()[0])
                    self.assertLessEqual(max(line.get_ydata()), ax.get_ylim()[1])
            plt.close(figure)
        figure = c.plot_comparison(c.comparison_rows([100]))
        self.assertEqual([len(ax.patches) for ax in figure.axes], [6, 6, 6])
        for ax in figure.axes:
            self.assertLessEqual(max(bar.get_height() for bar in ax.patches), ax.get_ylim()[1])
        plt.close(figure)

    def test_single_case_plots(self):
        rows = [r for r in c.comparison_rows([100]) if r['case'] == 'amplitude_only']
        for plot in (c.plot_comparison, c.plot_duration):
            figure = plot(rows)
            self.assertEqual(len(figure.axes), 1)
            self.assertIn('0.05 (fraction)', figure.axes[0].get_title())
            figure.canvas.draw()
            plt.close(figure)

    def test_invalid_grids_and_physical_parameters(self):
        for values in ([], [0], [-1], [np.inf], [[100]]):
            with self.assertRaises(ValueError):
                c.comparison_rows(values)
        for values in ([], [np.nan], [[0]]):
            with self.assertRaises(ValueError):
                c.amplitude_rows(values)
        with self.assertRaises(ValueError):
            c.comparison_rows([100], t1_ns=100, t2_ns=201)


if __name__ == '__main__':
    unittest.main()
