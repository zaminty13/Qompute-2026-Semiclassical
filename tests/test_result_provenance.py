import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from scipy.optimize import OptimizeResult

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from result_provenance import (REPORT_PATH, SUMMARY_PATH, MANIFEST_PATH,
    load_report, waveform_id, verify_results, optimizer_reporting)
from research_synthesis import Experiment, synthesize, evaluate, uncertainty_points
from option_b_benchmarks import candidate_segments, circuit_depth_benchmark


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.report=load_report(ROOT)

    def test_identity_ignores_metadata_but_detects_controls_and_config(self):
        changed=copy.deepcopy(self.report)
        changed['solver_reports']={'status':'unavailable'}
        changed['candidates'].reverse()
        self.assertEqual(waveform_id(changed),waveform_id(self.report))
        changed['config']['t1_ns']+=1
        self.assertNotEqual(waveform_id(changed),waveform_id(self.report))
        changed=copy.deepcopy(self.report)
        changed['candidates'][0]['segments'][0][1]+=.001
        self.assertNotEqual(waveform_id(changed),waveform_id(self.report))

    def test_legacy_artifacts_verified_without_rewriting(self):
        before=(ROOT/SUMMARY_PATH).read_bytes()
        summary=verify_results(ROOT,self.report)
        self.assertEqual(summary['config'],self.report['config'])
        self.assertEqual(before,(ROOT/SUMMARY_PATH).read_bytes())
        verify_results(ROOT,self.report,Path('results/option_b/qiskit_aer_validation.json'))
        old=json.loads((ROOT/'results/option_b/baseline_optimizer_report.json').read_text())
        with self.assertRaisesRegex(ValueError,'Legacy results'):
            verify_results(ROOT,old)
        self.assertEqual(optimizer_reporting(self.report)['status'],'unavailable')

    def test_changed_or_missing_legacy_results_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for path in (MANIFEST_PATH,SUMMARY_PATH):
                (root/path).parent.mkdir(parents=True,exist_ok=True)
                (root/path).write_bytes((ROOT/path).read_bytes())
            with (root/SUMMARY_PATH).open('ab') as stream:
                stream.write(b' ')
            with self.assertRaisesRegex(ValueError,'file hash'):
                verify_results(root,self.report)
            (root/SUMMARY_PATH).unlink()
            with self.assertRaises(FileNotFoundError):
                verify_results(root,self.report)

    def test_new_results_require_matching_identity_and_configuration(self):
        summary=verify_results(ROOT,self.report)
        summary['waveform_id']=waveform_id(self.report)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/SUMMARY_PATH).parent.mkdir(parents=True)
            def save():
                (root/SUMMARY_PATH).write_text(json.dumps(summary))
            save()
            self.assertEqual(verify_results(root,self.report),summary)
            summary['waveform_id']='wrong'
            save()
            with self.assertRaisesRegex(ValueError,'different waveform'):
                verify_results(root,self.report)
            summary['waveform_id']=waveform_id(self.report)
            summary['config']=dict(summary['config'],t1_ns=1.)
            save()
            with self.assertRaisesRegex(ValueError,'configuration'):
                verify_results(root,self.report)

    def test_saved_scientific_results_unchanged(self):
        ex=Experiment(**self.report['config'])
        candidate=next(row for row in self.report['candidates']
                       if row['name']=='BB1_constrained_synthesis')
        segments=candidate_segments(self.report)['synthesized']
        for held,key in ((False,'train_worst'),(True,'heldout_worst')):
            actual=evaluate(segments,ex,uncertainty_points(ex,held_out=held)).min()
            self.assertAlmostEqual(actual,candidate[key],places=12)
        saved=verify_results(ROOT,self.report)['depth_results']
        actual=circuit_depth_benchmark(self.report)
        self.assertEqual(len(saved),len(actual))
        for expected,row in zip(saved,actual):
            for key in ('success_probability','total_duration_ns','parity_3bit_mean_success'):
                self.assertAlmostEqual(row[key],expected[key],places=10)

    def test_future_solver_reporting_records_failure_and_residuals(self):
        candidate=next(row for row in self.report['candidates']
                       if row['name']=='BB1_constrained_synthesis')
        angles,phases=np.array(candidate['segments']).T
        vector=np.concatenate((angles/np.pi,phases))
        returned=OptimizeResult(x=vector,success=False,status=9,
                               message='Iteration limit',nit=65,nfev=123)
        with patch('research_synthesis.differential_evolution',return_value=returned), \
             patch('scipy.optimize.minimize',return_value=returned):
            result=synthesize(Experiment(**self.report['config']),maxiter=1,popsize=3)
        diagnostics=result['solver_reports']['SLSQP']
        self.assertFalse(diagnostics['success'])
        self.assertEqual(diagnostics['status'],9)
        self.assertEqual(len(diagnostics['advertised_fidelity_residuals']),9)
        self.assertGreater(min(diagnostics['advertised_fidelity_residuals']),0.)
        self.assertLess(min(diagnostics['slsqp_safety_residuals']),0.)
        self.assertAlmostEqual(diagnostics['advertised_fidelity_requirement'],.997)
        self.assertAlmostEqual(diagnostics['slsqp_safety_target'],.99703)
        self.assertEqual(result['waveform_id'],waveform_id(result))

    def test_builder_uses_selected_report_and_writes_identity(self):
        import build_option_b
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(build_option_b,'OUT',Path(folder)), \
             patch.object(build_option_b,'_plot_depth'), \
             patch.object(build_option_b,'_plot_multilevel'), \
             patch.object(build_option_b,'_plot_stress'), \
             patch.object(build_option_b,'_plot_cost'):
            result=build_option_b.build(quick=True)
            self.assertEqual(result['waveform_id'],waveform_id(self.report))
            self.assertEqual(result['source_report'],REPORT_PATH.as_posix())
            stored=json.loads((Path(folder)/'research_summary.json').read_text())
            self.assertEqual(stored['waveform_id'],result['waveform_id'])
            self.assertTrue((Path(folder)/'known_answer_circuit.csv').exists())
            self.assertTrue((Path(folder)/'05_parity_algorithm.png').exists())


if __name__=='__main__':
    unittest.main()
