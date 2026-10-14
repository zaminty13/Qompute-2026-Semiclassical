import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from result_provenance import load_report, waveform_id
from select_pulse import select_pulse


@unittest.skipUnless(importlib.util.find_spec('streamlit'), 'Install requirements-research.txt for dashboard tests')
class DashboardTests(unittest.TestCase):
    def page(self,path):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(ROOT/path),default_timeout=30)

    def test_default_pages_and_matching_identifiers(self):
        identity=waveform_id(load_report(ROOT))
        for path in ('app.py','pages/2_Research_Lab.py','pages/3_Reliability_Benchmarks.py'):
            with self.subTest(path=path):
                app=self.page(path).run()
                self.assertFalse(app.exception)
                self.assertFalse(app.error)
                if path!='app.py':
                    self.assertTrue(any(identity in x.value for x in app.caption))
        self.assertEqual([x.value for x in app.metric[:4]],['68.73%','95.57%','64.64%','4.32%'])

    def test_selector_inputs_units_and_no_qualifier(self):
        app=self.page('app.py').run()
        values={'Amplitude calibration error (%)':2.5,
                'Normalized detuning (\u0394/\u03a9)':.05,
                'Primitive X duration (ns)':150,'Minimum fidelity (%)':99.0}
        for widget in app.slider:
            if widget.label in values:
                widget.set_value(values[widget.label])
        app.number_input[0].set_value(200.)
        app.number_input[1].set_value(150.)
        app.run()
        self.assertFalse(app.exception)
        choice,rows=select_pulse(amplitude_error=.025,detuning_rad_per_ns=.05*np.pi/150,
            primitive_duration_ns=150.,t1_ns=200000.,t2_ns=150000.,min_fidelity=.99)
        metrics={x.label:x.value for x in app.metric}
        self.assertEqual(metrics['Selected fidelity'],f"{100*choice['fidelity']:.4f}%")
        self.assertEqual(metrics['Total pulse duration'],f"{choice['duration_ns']:.1f} ns")
        next(x for x in app.slider if x.label=='Minimum fidelity (%)').set_value(100.)
        app.run()
        self.assertTrue(any('No candidate reaches' in x.value for x in app.warning))
        self.assertIn('No feasible pulse',[x.value for x in app.metric])

    def test_research_sidebar_marks_saved_results_without_optimization(self):
        with patch('research_synthesis.synthesize') as optimizer:
            app=self.page('pages/2_Research_Lab.py').run()
            changes={'Amplitude uncertainty \u00b1 (%)':6.,
                     'Normalized detuning uncertainty \u00b1':.05,
                     'Required worst sampled fidelity (%)':99.8,
                     'T\u2081 (\u00b5s)':210,'T\u2082 (\u00b5s)':160}
            for widget in app.slider:
                if widget.label in changes:
                    widget.set_value(changes[widget.label])
            app.run()
            self.assertFalse(app.exception)
            self.assertTrue(any('previous experiment' in x.value for x in app.warning))
            optimizer.assert_not_called()

    def test_missing_report_and_results_fail_gracefully(self):
        with patch('result_provenance.load_report',side_effect=FileNotFoundError('missing report')):
            for path in ('pages/2_Research_Lab.py','pages/3_Reliability_Benchmarks.py'):
                app=self.page(path).run()
                self.assertFalse(app.exception)
                self.assertFalse(app.metric)
                self.assertTrue(app.warning or app.error)
        with patch('result_provenance.verify_results',side_effect=FileNotFoundError('missing summary')):
            app=self.page('pages/3_Reliability_Benchmarks.py').run()
            self.assertFalse(app.exception)
            self.assertTrue(app.error)
            self.assertFalse(app.metric)

    def test_new_session_waveform_hides_incompatible_saved_results(self):
        report=copy.deepcopy(load_report(ROOT))
        report['config']['t1_ns']+=1000
        app=self.page('pages/3_Reliability_Benchmarks.py')
        app.session_state['research_report']=report
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('incompatible' in x.value for x in app.error))
        self.assertFalse(app.metric)

    def test_stale_aer_results_hidden(self):
        app=self.page('pages/3_Reliability_Benchmarks.py')
        app.session_state['option_b_aer_checks']={'waveform_id':'old'}
        app.run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Previous Aer results are incompatible' in x.value for x in app.warning))
        self.assertEqual(len(app.metric),4)


if __name__=='__main__':
    unittest.main()
