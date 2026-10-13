"""Adversarial regression tests for the Option B reliability experiments."""
import json
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from option_b_benchmarks import (
    candidate_segments, shared_multilevel_comparison, multilevel_sweep,
    identity_circuit_success, parity_truth_table_success,
    circuit_depth_benchmark, stress_test_report, qiskit_aer_circuit_checks)
from research_synthesis import Experiment, BASELINES, X, channel, segment_duration_ns

REPORT_PATH=ROOT/'results'/'option_b'/'baseline_optimizer_report.json'

class OptionBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report=json.loads(REPORT_PATH.read_text(encoding='utf-8'))
        cls.ex=Experiment(**cls.report['config'])

    def test_original_waveform_identity_and_fixed_amplitude(self):
        segs=candidate_segments(self.report)
        self.assertEqual(tuple(segs),('primitive','BB1','CORPSE','synthesized'))
        self.assertEqual(len(segs['synthesized']),5)
        self.assertTrue(np.allclose(segs['BB1'],BASELINES['BB1']))
        self.assertAlmostEqual(segment_duration_ns(segs['synthesized'],self.ex),345.677183355,places=4)

    def test_no_fabricated_synthesized_result(self):
        with self.assertRaisesRegex(ValueError,'Missing unique'):
            candidate_segments({'candidates':[{'name':'primitive'}]})

    def test_ideal_known_answer_and_truth_table(self):
        s=np.kron(X.conj(),X)
        for depth in range(17):
            self.assertAlmostEqual(identity_circuit_success(s,depth),1.,places=12)
        parity=parity_truth_table_success(s)
        self.assertEqual(len(parity['truth_table']),8)
        self.assertAlmostEqual(parity['mean_success'],1.,places=12)
        self.assertEqual([r['expected_parity'] for r in parity['truth_table']],
                         [0,1,1,0,1,0,0,1])

    def test_known_answer_invalid_parameters(self):
        with self.assertRaises(ValueError):identity_circuit_success(np.eye(3),3)
        with self.assertRaises(ValueError):identity_circuit_success(np.eye(4),-1)
        with self.assertRaises(ValueError):identity_circuit_success(np.eye(4),True)
        with self.assertRaises(ValueError):parity_truth_table_success(np.eye(4),0)

    def test_parity_correlated_model_formula(self):
        # Independently prepared input 1 bits, ideal CX gates. For two prepared
        # 1 bits, parity failure requires exactly one preparation flip.
        s=channel(BASELINES['primitive'],self.ex,.05,0.)
        e=1-identity_circuit_success(s,1)
        records=parity_truth_table_success(s)['truth_table']
        two=next(r for r in records if r['input_bits']=='110')
        self.assertAlmostEqual(two['success_probability'],1-2*e*(1-e),places=12)

    def test_shared_multilevel_controls_and_metrics(self):
        rows=shared_multilevel_comparison(self.report)
        self.assertEqual(len(rows),4)
        self.assertEqual({r['candidate'] for r in rows},{'primitive','BB1','CORPSE','synthesized'})
        for r in rows:
            self.assertTrue(0<=r['final_leakage']<=r['peak_leakage']+1e-9)
            self.assertTrue(0<=r['fidelity_unconditional']<=1.)
        # Under this explicitly frozen surrogate configuration BB1 loses to
        # the shorter primitive; don't claim two-level ordering generalizes.
        ref={r['candidate']:r for r in rows}
        self.assertLess(ref['BB1']['fidelity_unconditional'],ref['primitive']['fidelity_unconditional'])
        # Disconnecting the 1-2 coupling should eliminate leakage.
        disconnected=shared_multilevel_comparison(self.report,coupling_ratio=0.)
        self.assertLess(max(r['final_leakage'] for r in disconnected),1e-10)

    def test_matched_sweep_does_not_conflate_coherent_and_noisy(self):
        rows=multilevel_sweep(self.report,alphas=(-4.,-3.),coupling_ratio=.8)
        self.assertEqual(len(rows),8)
        self.assertEqual({r['alpha_over_omega'] for r in rows},{-4.,-3.})

    def test_depth_benchmark_persists_coherent_error(self):
        rows=circuit_depth_benchmark(self.report,depths=(1,8,32))
        self.assertEqual(len(rows),4*4*3)
        subset={r['candidate']:r for r in rows
                if r['case']=='combined corner' and r['depth']==32}
        self.assertGreater(subset['BB1']['success_probability'],.9)
        self.assertLess(subset['synthesized']['success_probability'],.1)
        self.assertEqual(subset['BB1']['total_segments'],128)
        self.assertEqual(subset['synthesized']['total_segments'],160)
        self.assertGreater(subset['BB1']['total_duration_ns'],subset['synthesized']['total_duration_ns'])

    def test_dense_and_shifted_stress(self):
        rows=stress_test_report(self.report,grid_size=11,n_random=32)
        self.assertEqual(len(rows),12)
        in_domain={r['candidate']:r for r in rows if r['scenario']=='dense_in_domain'}
        self.assertTrue(in_domain['synthesized']['passes_all_sampled'])
        self.assertFalse(in_domain['primitive']['passes_all_sampled'])
        out={r['candidate']:r for r in rows if r['scenario']=='shifted_calibration_out_of_domain'}
        self.assertGreater(out['synthesized']['fraction_below_threshold'],0)

    @unittest.skipUnless(__import__('importlib').util.find_spec('qiskit') and
                         __import__('importlib').util.find_spec('qiskit_aer'),
                         'Qiskit Aer not installed in this execution environment')
    def test_qiskit_aer_parity_and_depth(self):
        result=qiskit_aer_circuit_checks(self.report,shots=1024,depth=8)
        self.assertEqual(result['num_circuits'],5*9)
        self.assertTrue(result['all_consistent'])
        identity=[row for row in result['cases'] if row['task']=='identity']
        self.assertEqual(len(identity),5)
        self.assertEqual({row['expected_bit'] for row in identity},{'0'})

    @unittest.skipUnless(__import__('importlib').util.find_spec('qiskit') and
                         __import__('importlib').util.find_spec('qiskit_aer'),
                         'Qiskit Aer not installed in this execution environment')
    def test_qiskit_aer_32_gate_headline_alignment(self):
        result=qiskit_aer_circuit_checks(self.report,shots=2048,depth=32)
        identity={row['candidate']:row for row in result['cases'] if row['task']=='identity'}
        self.assertEqual(len(identity),5)
        self.assertEqual(identity['ideal']['predicted_probability'],1.0)
        self.assertTrue(result['all_consistent'])
        expected={row['candidate']:row['success_probability']
                  for row in circuit_depth_benchmark(self.report,depths=(32,))
                  if row['case']=='combined corner'}
        for name,p in expected.items():
            self.assertAlmostEqual(identity[name]['predicted_probability'],p,places=10)
        self.assertEqual({row['expected_bit'] for row in identity.values()},{'0'})

if __name__=='__main__':unittest.main()
