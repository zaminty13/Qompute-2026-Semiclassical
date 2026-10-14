import csv
import hashlib
import itertools
import json
import random
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from qiskit.quantum_info import Kraus, SuperOp, Operator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
import rb
from decoherence import sequence_superop
from pulses import SEQUENCE_NAMES, sequence_unitary
from compare_rb_selector import compare_study
from plot_rb import build_study

OMEGA = np.pi / 100


class SurvivalStudyTests(unittest.TestCase):
    def test_seed_replay_and_global_rng_untouched(self):
        state = random.getstate()
        a = rb.sample_sequences((0, 2, 7), 20, 2026)
        self.assertEqual(a, rb.sample_sequences((0, 2, 7), 20, 2026))
        self.assertNotEqual(a, rb.sample_sequences((0, 2, 7), 20, 2027))
        self.assertEqual(state, random.getstate())
        self.assertEqual(rb.X_PROBABILITY, rb.X_CHOICES.count(True)/len(rb.X_CHOICES))

    def test_invalid_configurations(self):
        for lengths, trials, seed in [((), 2, 1), ((2, 2), 2, 1), ((-1,), 2, 1),
                                     ((True,), 2, 1), ((2,), 0, 1), ((2,), 1, 1),
                                     ((2,), 2.5, 1), ((2,), 2, -1)]:
            with self.subTest((lengths, trials, seed)), self.assertRaises(ValueError):
                rb.sample_sequences(lengths, trials, seed)
        with self.assertRaises(ValueError):
            rb.sequence_cost([1], 'primitive', OMEGA)
        with self.assertRaises(ValueError):
            rb.average_survival_probability(2, 0, 'primitive', OMEGA)
        with self.assertRaises(ValueError):
            rb.run_survival_study(primitive_duration_ns=0)
        with self.assertRaises(ValueError):
            rb.run_survival_study(lengths=(2,), num_trials=2, t1_ns=1, t2_ns=3)

    def test_recovery_counts_segments_and_durations(self):
        for name, duration, segments in [('primitive', 100, 1), ('BB1', 500, 4), ('CORPSE', 1300/3, 3)]:
            for flips, k in [((), 0), ((False, False), 0), ((True, False), 1),
                             ((True, True), 2), ((True, False, True, True), 3)]:
                cost = rb.sequence_cost(flips, name, OMEGA)
                self.assertEqual(cost['executed_x_count'], k+k%2)
                self.assertEqual(cost['recovery_x_count'], k%2)
                self.assertEqual(cost['physical_segment_count'], segments*(k+k%2))
                self.assertAlmostEqual(cost['duration_ns'], duration*(k+k%2))

    def test_ideal_even_and_odd_recovery_both_states(self):
        for name in SEQUENCE_NAMES:
            for m in range(4):
                for flips in itertools.product((False, True), repeat=m):
                    s = rb.sequence_to_superop(flips, name, OMEGA)
                    np.testing.assert_allclose(s.data, np.eye(4), atol=1e-12)
                    for state in (0, 1):
                        self.assertAlmostEqual(rb.count_survival(s.data, 1, state), 1.)

    def test_same_count_order_and_zero_time_identity(self):
        for name in SEQUENCE_NAMES:
            reference = rb.sequence_to_superop([True, True], name, OMEGA, .05, .003, 30000, 20000).data
            for flips in [(True, False, True), (False, True, True), (True, True, False)]:
                actual = rb.sequence_to_superop(flips, name, OMEGA, .05, .003, 30000, 20000).data
                np.testing.assert_allclose(actual, reference, atol=1e-13)
            np.testing.assert_allclose(rb.sequence_to_superop([False]*8, name, OMEGA, .05, .003, 30000, 20000).data, np.eye(4))

    def test_unitary_and_kraus_composition_independently(self):
        flips = (True, False, True, True)
        for name in SEQUENCE_NAMES:
            u = sequence_unitary(name, OMEGA, .05, .003)
            expected = u @ u @ u @ u
            np.testing.assert_allclose(rb.sequence_to_unitary(flips, name, OMEGA, .05, .003), expected, atol=1e-13)
            noisy = sequence_superop(name, OMEGA, .05, .003, t1_ns=30000, t2_ns=20000)
            kraus = Kraus(noisy).data
            rho = np.diag([1., 0.]).astype(complex)
            for _ in range(4):
                rho = sum(k @ rho @ k.conj().T for k in kraus)
            composed = rb.sequence_to_superop(flips, name, OMEGA, .05, .003, 30000, 20000)
            self.assertAlmostEqual(rho[0,0].real, rb.survival_probability_from_superop(composed), places=12)
            np.testing.assert_allclose(composed.data, np.linalg.matrix_power(noisy.data, 4), atol=1e-13)
            coherent = rb.sequence_to_superop(flips, name, OMEGA, .05, .003)
            np.testing.assert_allclose(coherent.data, SuperOp(Operator(expected)).data, atol=1e-12)

    def test_binomial_matches_explicit_enumeration(self):
        for name in SEQUENCE_NAMES:
            channel = sequence_superop(name, OMEGA, .05, .003, t1_ns=30000, t2_ns=20000).data
            for m in (0, 1, 2, 4):
                for q in (rb.X_PROBABILITY, .3):
                    values, weights = [], []
                    for flips in itertools.product((False, True), repeat=m):
                        s = rb.sequence_to_superop(flips, name, OMEGA, .05, .003, 30000, 20000)
                        values.append(rb.survival_probability_from_superop(s))
                        k = sum(flips)
                        weights.append(q**k*(1-q)**(m-k))
                    mean = np.dot(weights, values)
                    exact = rb.exact_survival(channel, m, q=q)
                    self.assertAlmostEqual(exact['exact_mean_survival'], mean, places=12)
                    self.assertAlmostEqual(exact['exact_sequence_variance'], np.dot(weights, (np.array(values)-mean)**2), places=13)

    def test_mean_duration_is_not_individual_duration(self):
        study = rb.run_survival_study(lengths=(4,), num_trials=30)
        for row in study['summary']:
            self.assertAlmostEqual(row['exact_mean_executed_x'], 2.5)
            self.assertLess(row['min_duration_ns'], row['max_duration_ns'])
            self.assertAlmostEqual(row['exact_mean_duration_ns'], 2.5*row['x_duration_ns'])

    def test_matched_samples_uncertainty_and_exact_variance(self):
        study = rb.run_survival_study(lengths=(2, 8), num_trials=512)
        for m in (2, 8):
            sequences = []
            for name in SEQUENCE_NAMES:
                rows = [r for r in study['samples'] if r['length']==m and r['pulse_type']==name]
                sequences.append([r['sequence'] for r in rows])
                values = [r['survival_probability'] for r in rows]
                summary = next(r for r in study['summary'] if r['length']==m and r['pulse_type']==name)
                self.assertAlmostEqual(summary['mean_survival'], np.mean(values))
                self.assertAlmostEqual(summary['sequence_standard_error'], np.std(values, ddof=1)/np.sqrt(512))
                self.assertAlmostEqual(summary['exact_standard_error']**2, summary['exact_sequence_variance']/512)
                self.assertLess(abs(summary['mean_survival']-summary['exact_mean_survival']), 5*summary['exact_standard_error']+1e-12)
                self.assertTrue(all(0 <= x <= 1 for x in values))
            self.assertEqual(sequences[0], sequences[1])
            self.assertEqual(sequences[1], sequences[2])

    def test_relaxation_return_is_state_dependent(self):
        channel = sequence_superop('primitive', OMEGA, -1., 0., t1_ns=1000., t2_ns=2000.).data
        self.assertAlmostEqual(rb.count_survival(channel, 2, 0), 1.)
        self.assertAlmostEqual(rb.count_survival(channel, 2, 1), np.exp(-.2))

    def test_selector_objective_and_survival_ranking(self):
        rows = compare_study(rb.run_survival_study(lengths=(32,), num_trials=128, detuning_rad_per_ns=0.))
        self.assertEqual({r['selector_choice'] for r in rows}, {'primitive'})
        self.assertEqual(max(rows, key=lambda r:r['direct_fidelity'])['pulse_type'], 'primitive')
        self.assertEqual(max(rows, key=lambda r:r['exact_mean_survival'])['pulse_type'], 'BB1')
        self.assertNotIn('rb_error_per_gate', rows[0])

    def test_provenance_survives_checkout_line_endings(self):
        from plot_rb import _file_sha256
        with tempfile.TemporaryDirectory() as folder:
            for suffix in ('.py', '.csv'):
                path = Path(folder)/('source'+suffix)
                path.write_bytes(b'a\nb\n')
                expected = _file_sha256(path)
                path.write_bytes(b'a\r\nb\r\n')
                self.assertEqual(_file_sha256(path), expected)
            path = Path(folder)/'image.png'
            path.write_bytes(b'a\r\nb')
            self.assertEqual(_file_sha256(path), hashlib.sha256(path.read_bytes()).hexdigest())

    def test_outputs_reproducible_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder)/'a', Path(folder)/'b'
            build_study(a, num_trials=8)
            build_study(b, num_trials=8)
            for name in ('summary.csv', 'samples.csv', 'selector_comparison.csv', 'metadata.json'):
                self.assertEqual((a/name).read_bytes(), (b/name).read_bytes())
            metadata = json.loads((a/'metadata.json').read_text())
            for name, digest in metadata['files_sha256'].items():
                data = (a/name).read_bytes()
                if name.endswith('.csv'):
                    data = data.replace(b'\r\n', b'\n')
                self.assertEqual(hashlib.sha256(data).hexdigest(), digest)
            with (a/'samples.csv').open() as stream:
                samples = list(csv.DictReader(stream))
            self.assertEqual(len(samples), 4*3*5*8)
            self.assertIn('recovery_x_count', samples[0])
            self.assertIn('physical_segment_count', samples[0])
            self.assertTrue(all((a/name).stat().st_size > 1000 for name in metadata['files_sha256'] if name.endswith('.png')))
            with self.assertRaises(FileExistsError):
                build_study(a, num_trials=8)


if __name__ == '__main__':
    unittest.main()
