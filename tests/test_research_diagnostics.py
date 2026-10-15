"""Regression tests for model-based post-selection audit."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from research_synthesis import Experiment, synthesize
from research_diagnostics import summarize_selection, independent_sample_stress

class AuditTests(unittest.TestCase):
    def basic_report(self):
        ex = Experiment(amplitude_center=0., amplitude_width=.01,
                        detuning_width_over_omega=.005, min_fidelity=.98)
        return synthesize(ex, run_optimizer=False)

    def test_reference_and_tie_reporting(self):
        report = self.basic_report()
        summary = summarize_selection(report)
        self.assertEqual(summary['winner'], 'seed_1')
        self.assertAlmostEqual(summary['winner_duration_ns'], 100)
        self.assertEqual(summary['fastest_passing_reference'], 'primitive')
        self.assertIsNone(summary['winner_solver_success'])

    def test_stress_preserves_winner_and_excludes_selection_points(self):
        report = self.basic_report()
        winner = report['winner']
        output = independent_sample_stress(report, grid_size=7, random_count=4)
        self.assertGreater(output['total_points'], 4)
        self.assertEqual(output['points_reused_from_training_or_selection'], 0)
        self.assertEqual(report['winner'], winner)
        self.assertTrue(any(c['candidate'] == winner for c in output['candidates']))

    def test_near_tie_detection_and_invalid_stored_winner(self):
        report = self.basic_report()
        first = next(c for c in report['candidates'] if c['name'] == 'seed_1')
        report['candidates'].append(dict(first, name='BB1_constrained_synthesis',
                                         duration_ns=first['duration_ns'] + .001))
        report['solver_reports'] = {'SLSQP_by_seed': {
            'BB1': {'success': False, 'message': 'Iteration limit reached',
                    'slsqp_safety_residuals': [-0.00001]}}}
        summary = summarize_selection(report)
        self.assertIn('BB1_constrained_synthesis', summary['near_tied_candidates'])
        report['winner'] = 'BB1_constrained_synthesis'
        with self.assertRaises(ValueError):
            summarize_selection(report)

if __name__ == '__main__':
    unittest.main()
