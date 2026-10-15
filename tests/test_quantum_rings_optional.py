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
