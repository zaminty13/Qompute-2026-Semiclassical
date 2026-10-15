import math
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from quantum_rings_optional import DEPTHS,expected_probability,compare

class OptionalRingsTests(TestCase):
    def test_ideal_even_depth(self):
        for n in DEPTHS:
            self.assertAlmostEqual(expected_probability(n,0.),1.,places=12)
    def test_overrotation(self):
        self.assertAlmostEqual(expected_probability(8,.05),math.cos(.2*math.pi)**2,places=12)
    def test_opt_in(self):
        with patch("quantum_rings_optional.run_aer",return_value=[1.]*5), \
             patch("quantum_rings_optional.run_quantum_rings") as rings:
            rows=compare()
            self.assertEqual(len(rows),5)
            self.assertTrue(all(row["quantum_rings"] is None for row in rows))
            rings.assert_not_called()

class IsolatedRingsTests(TestCase):
    def test_quantum_rings_runs_in_subprocess(self):
        from quantum_rings_optional import run_quantum_rings_isolated

        with patch("subprocess.run") as process:
            process.return_value.returncode = 0
            process.return_value.stdout = "[0.9, 0.8, 0.7, 0.6, 0.5]"

            values = run_quantum_rings_isolated(error=0.05, shots=512)

            self.assertEqual(len(values), 5)
            self.assertEqual(values[0], 0.9)
            process.assert_called_once()

    def test_subprocess_failure_is_reported(self):
        from quantum_rings_optional import run_quantum_rings_isolated

        with patch("subprocess.run") as process:
            process.return_value.returncode = 1
            process.return_value.stderr = "Simulator failed"

            with self.assertRaisesRegex(RuntimeError, "Simulator failed"):
                run_quantum_rings_isolated()
