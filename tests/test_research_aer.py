import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from research_synthesis import Experiment,BASELINES

class ResearchAerTests(unittest.TestCase):
    def test_qiskit_six_state_experiment(self):
        try:
            import qiskit
            import qiskit_aer
        except ImportError:
            self.skipTest('Qiskit Aer not available in build environment')
        from research_qiskit import six_state_aer_check
        ex=Experiment()
        outcome=six_state_aer_check(BASELINES['primitive'],ex,shots=2048,seed=123)
        self.assertEqual(outcome['total_shots'],6*2048)
        self.assertEqual(len(outcome['states']),6)
        self.assertLess(outcome['analytical_vs_qiskit_error'],1e-10)
        self.assertLess(abs(outcome['shot_estimate']-outcome['predicted_fidelity']),.014)

if __name__=='__main__':unittest.main()
