"""Standalone core tests plus Qiskit integration checks on the user's environment."""
import sys
from pathlib import Path
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from research_synthesis import (Experiment, X, BASELINES, channel, evaluate,
    fidelity_from_superop, segment_duration_ns, uncertainty_points, synthesize,
    qiskit_reference_check)


class ResearchSynthesisTests(unittest.TestCase):
    def test_ideal_X_analytic(self):
        ex=Experiment(t1_ns=1e12,t2_ns=1e12)
        s=channel(BASELINES['primitive'],ex,0,0)
        self.assertAlmostEqual(fidelity_from_superop(s),1.,places=8)
        self.assertTrue(np.all(np.isfinite(s)))
        for eps in (-.10,-.05,.05,.1):
            actual=fidelity_from_superop(channel(BASELINES['primitive'],ex,eps,0))
            analytical=1-(2/3)*np.sin(np.pi*eps/2)**2
            self.assertAlmostEqual(actual,analytical,places=8)

    def test_duration_and_standard_sequences(self):
        ex=Experiment()
        self.assertAlmostEqual(segment_duration_ns(BASELINES['primitive'],ex),100)
        self.assertAlmostEqual(segment_duration_ns(BASELINES['BB1'],ex),500)
        self.assertAlmostEqual(segment_duration_ns(BASELINES['CORPSE'],ex),1300/3)

    def test_training_holdout_separation(self):
        ex=Experiment()
        train=uncertainty_points(ex)
        held=uncertainty_points(ex,held_out=True)
        self.assertEqual(train.shape,(9,2))
        self.assertEqual(held.shape,(96,2))
        self.assertFalse(any(np.allclose(t,h,atol=1e-12) for t in train for h in held))
        self.assertTrue(np.all(held[:,0]<=ex.amplitude_center+ex.amplitude_width+1e-12))
        self.assertTrue(np.all(held[:,1]>=ex.detuning_center_over_omega-ex.detuning_width_over_omega-1e-12))
        self.assertEqual(len(evaluate(BASELINES['BB1'],ex,held)),96)

    def test_config_guardrails(self):
        with self.assertRaises(ValueError): Experiment(t1_ns=100,t2_ns=250)
        with self.assertRaises(ValueError): Experiment(amplitude_width=-.05)
        with self.assertRaises(ValueError): Experiment(min_fidelity=1.01)
        with self.assertRaises(ValueError): Experiment(primitive_ns=0)
        with self.assertRaises(ValueError): Experiment(seed=True)

    def test_local_search_uses_valid_candidate_lengths(self):
        ex=Experiment(amplitude_center=0.,amplitude_width=.05,
                      detuning_width_over_omega=.04)
        # Exercise five-segment parameter mapping without an expensive search.
        out=synthesize(ex,run_optimizer=False)
        self.assertTrue(any(c['name']=='BB1' for c in out['candidates']))
        self.assertEqual(out['n_heldout'],96)
        for row in out['candidates']:
            self.assertGreater(row['duration_ns'],0)
            self.assertTrue(0<=row['heldout_worst']<=1)
        chosen = next(c for c in out['candidates']
                      if c['name'] == out['winner'])

        qualifying = [
            c for c in out['candidates']
            if c['train_pass'] and c['heldout_pass']
        ]

        self.assertTrue(chosen['train_pass'] and chosen['heldout_pass'])

        self.assertAlmostEqual(
            chosen['duration_ns'],
            min(c['duration_ns'] for c in qualifying),
            places=8
        )



    def test_qiskit_reference(self):
        try:
            import qiskit
            import decoherence
        except ImportError:
            self.skipTest('Qiskit/team decoherence.py not available in build environment')
        ex=Experiment()
        for seq in (BASELINES['primitive'],BASELINES['BB1']):
            result=qiskit_reference_check(seq,ex,.03,.02)
            self.assertLess(result['channel_max_abs_error'],2e-10)
            self.assertLess(result['fidelity_difference'],1e-10)


if __name__=='__main__':unittest.main()
