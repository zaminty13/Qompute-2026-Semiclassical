"""Quick tests for the optional Qiskit Aer measurement layer."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aer_validation import PREPARATIONS, _preparation, estimate_gate_fidelity


class AerValidationTests(unittest.TestCase):
    def test_six_cardinal_states(self):
        self.assertEqual(len(PREPARATIONS), 6)
        with self.assertRaises(ValueError):
            _preparation("unknown")

    def test_ideal_x_returns_unit_fidelity(self):
        r = estimate_gate_fidelity(
            "primitive", amplitude_error=0.0, detuning_rad_per_ns=0.0,
            primitive_duration_ns=100.0, t1_ns=float("inf"),
            t2_ns=float("inf"), shots_per_state=128,
        )
        self.assertAlmostEqual(r["predicted_fidelity"], 1.0, places=10)
        self.assertAlmostEqual(r["shot_estimated_fidelity"], 1.0, places=10)
        self.assertEqual(r["total_shots"], 768)

    def test_noisy_shots_agree_with_model_within_sampling_tolerance(self):
        r = estimate_gate_fidelity(
            "BB1", amplitude_error=0.05, detuning_rad_per_ns=0.0,
            primitive_duration_ns=100.0, t1_ns=30000.0,
            t2_ns=20000.0, shots_per_state=512,
        )
        self.assertLess(abs(r["shot_estimated_fidelity"] - r["predicted_fidelity"]), 0.035)

    def test_invalid_shots(self):
        with self.assertRaises(ValueError):
            estimate_gate_fidelity(
                "primitive", amplitude_error=0, detuning_rad_per_ns=0,
                primitive_duration_ns=100, t1_ns=30000, t2_ns=20000,
                shots_per_state=0,
            )


if __name__ == "__main__":
    unittest.main()
