import unittest
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from research_synthesis import BASELINES
from research_leakage import hamiltonian,propagate,qiskit_sample_leakage


class ResearchLeakageTests(unittest.TestCase):
    def test_no_leakage_if_no_12_coupling(self):
        out=propagate(BASELINES['primitive'],coupling_ratio=0.,steps_per_segment=3)
        self.assertAlmostEqual(out['fidelity_unconditional'],1.,places=12)
        self.assertAlmostEqual(out['peak_leakage'],0.,places=12)
        self.assertAlmostEqual(out['final_leakage'],0.,places=12)

    def test_unitarity_and_leakage_range(self):
        for name in ('primitive','BB1','CORPSE'):
            out=propagate(BASELINES[name],steps_per_segment=4)
            self.assertTrue(np.allclose(out['unitary'].conj().T @ out['unitary'],np.eye(4),atol=1e-10))
            self.assertGreaterEqual(out['peak_leakage']+1e-10,out['final_leakage'])
            self.assertTrue(0<=out['fidelity_unconditional']<=1)
            self.assertTrue(0<=out['final_leakage']<=1)
            self.assertAlmostEqual(out['duration_ns'],sum(a for a,p in BASELINES[name])*100/np.pi,places=8)

    def test_hermitian_hamiltonian(self):
        h=hamiltonian(.03,.9,-.03,.05,-3.,np.sqrt(2))
        self.assertTrue(np.allclose(h,h.conj().T,atol=1e-14))

    def test_errors(self):
        with self.assertRaises(ValueError):propagate(BASELINES['BB1'],coupling_ratio=-1)
        with self.assertRaises(ValueError):propagate([(0.,0.)])
        with self.assertRaises(ValueError):propagate(BASELINES['BB1'],steps_per_segment=1)

    def test_two_qubit_aer_leakage(self):
        try:
            import qiskit
            import qiskit_aer
        except ImportError:
            self.skipTest('Qiskit Aer not available in build environment')
        result=propagate(BASELINES['primitive'],steps_per_segment=4)
        samples=qiskit_sample_leakage(result['unitary'],shots=4096,seed=100)
        self.assertEqual(len(samples['rows']),2)
        self.assertLess(abs(samples['estimated_mean_leakage'] - result['final_leakage']),.025)


if __name__=='__main__':unittest.main()
