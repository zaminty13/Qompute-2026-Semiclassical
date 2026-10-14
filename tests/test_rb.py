import random
import sys
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import rb
import plot_rb
import pulses as p

OMEGA = np.pi / 100

class RBTests(unittest.TestCase):
  def test_zero_error_returns_one(self):
    random.seed(0)
    for pulse_type in ['primitive', 'BB1', 'CORPSE']:
      with self.subTest(pulse_type=pulse_type):
        probability = rb.average_survival_probability(10, 50, pulse_type,
                                                      OMEGA, amplitude_error=0.0,
                                                      detuning_rad_per_ns=0.0)
        self.assertAlmostEqual(probability, 1.0, places=10)
  def test_needs_inverting_gate(self):
    cases = [
      ([], False),
      ([True], True),
      ([True, True], False),
      ([True, False, True], False),
      ([True, True, True], True),
    ]
    for sequence, expected in cases:
      with self.subTest(sequence=sequence):
        self.assertEqual(rb.needs_inverting_gate(sequence), expected)

  def test_zero_error_infinite_coherence_times_returns_once(self):
    random.seed(0)
    for pulse_type in ['primitive', 'BB1', 'CORPSE']:
      with self.subTest(pulse_type=pulse_type):
        probability = rb.average_survival_probability_with_decoherence(
          10, 50, pulse_type, OMEGA, amplitude_error=0.0, detuning_rad_per_ns=0.0,
          t1_ns=np.inf, t2_ns=np.inf)
        self.assertAlmostEqual(probability, 1.0, places=9)

  def test_survival_probability_known_matrices(self):
    self.assertAlmostEqual(rb.survival_probability(p.IDENTITY), 1.0, places=14)
    self.assertAlmostEqual(rb.survival_probability(p.PAULI_X), 0.0, places=14)

  def test_rb_decay_curve_structure(self):
    random.seed(0)
    lengths = [2,4,8]
    results = rb.rb_decay_curve(lengths, 20, 'primitive', OMEGA, amplitude_error=0.05,
                                detuning_rad_per_ns=0.0)
    self.assertEqual(len(results), len(lengths))
    for (returned_length, probability), expected_length in zip(results, lengths):
      with self.subTest(expected_length=expected_length):
        self.assertEqual(returned_length, expected_length)
        self.assertGreaterEqual(probability, 0.0)
        self.assertLessEqual(probability, 1.0)

  def test_exponential_decay_known_values(self):
    self.assertAlmostEqual(plot_rb.exponential_decay(0,1.0,0.5, 0.0), 1.0)
    self.assertAlmostEqual(plot_rb.exponential_decay(2, 1.0, 0.5, 0.0), 0.25)
    self.assertAlmostEqual(plot_rb.exponential_decay(3, 2.0, 0.5, 0.1), 0.35)

  def test_fit_decay_recovers_known_params(self):
    true_A, true_p, true_B = 0.9, 0.95, 0.05
    lengths = [2,4,8,16,32]
    decay_curve_data = [(m, plot_rb.exponential_decay(m, true_A, true_p, true_B)) for m in lengths]
    A, p, B, r = plot_rb.fit_decay(decay_curve_data)
    self.assertAlmostEqual(A, true_A, places=6)
    self.assertAlmostEqual(p, true_p, places=6)
    self.assertAlmostEqual(B, true_B, places=6)
    self.assertAlmostEqual(r, (1-true_p)/2, places=6)

  def test_decoherence_reduces_survival_probability(self):
    for pulse_type in ['primitive', 'BB1', 'CORPSE']:
      with self.subTest(pulse_type=pulse_type):
        random.seed(1)
        baseline = rb.average_survival_probability_with_decoherence(
          20, 50, pulse_type, OMEGA, amplitude_error=0.0, detuning_rad_per_ns=0.0,
          t1_ns=np.inf, t2_ns=np.inf
        )
        random.seed(1)
        with_decoherence = rb.average_survival_probability_with_decoherence(
          20,50,pulse_type, OMEGA, amplitude_error=0.0, detuning_rad_per_ns=0.0,
          t1_ns=5000, t2_ns=3000
        )
        self.assertLess(with_decoherence, baseline)

if __name__ == '__main__':
  unittest.main()
