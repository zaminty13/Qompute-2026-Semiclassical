import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analyze_crossovers import find_crossovers, favorable_intervals, preference


class CrossoverTests(unittest.TestCase):
    def test_sign_change_through_exact_grid_zero(self):
        grid = np.linspace(-1, 1, 11)
        roots = find_crossovers(lambda x: x, grid, grid)
        self.assertEqual(len(roots), 1)
        self.assertAlmostEqual(roots[0]['coordinate'], 0)
        self.assertEqual(roots[0]['left_preferred'], 'primitive')
        self.assertEqual(roots[0]['right_preferred'], 'composite')

    def test_touch_and_small_noise_are_not_crossovers(self):
        grid = np.linspace(-1, 1, 11)
        self.assertEqual(find_crossovers(lambda x: x*x, grid, grid*grid), [])
        values = np.sin(grid*20)*1e-12
        self.assertEqual(find_crossovers(lambda x: np.sin(x*20)*1e-12, grid, values), [])
        self.assertEqual(preference(1e-10), 'tie')
        self.assertEqual(preference(-1e-10), 'tie')

    def test_multiple_changes_and_finer_grid_reveals_narrow_interval(self):
        function = lambda x: (x-.31)*(x-.39)
        coarse = np.linspace(0, 1, 6)
        fine = np.linspace(0, 1, 101)
        self.assertEqual(find_crossovers(function, coarse, function(coarse)), [])
        roots = find_crossovers(function, fine, function(fine))
        np.testing.assert_allclose([r['coordinate'] for r in roots], [.31, .39], atol=1e-12)

    def test_tolerance_intervals_include_ties(self):
        grid = np.linspace(-1, 1, 21)
        intervals = favorable_intervals(lambda x: x, grid, grid, tolerance=.05)
        self.assertEqual([r['preferred'] for r in intervals], ['primitive', 'tie', 'composite'])
        np.testing.assert_allclose([(r['left'], r['right']) for r in intervals],
                                   [(-1, -.05), (-.05, .05), (.05, 1)], atol=1e-12)
        touches = favorable_intervals(lambda x: x*x, grid, grid*grid, tolerance=.01)
        self.assertEqual([r['preferred'] for r in touches], ['composite', 'tie', 'composite'])

    def test_invalid_samples_are_rejected(self):
        for grid, values in [([1,0],[1,0]), ([0,1],[0,np.nan]), ([0],[0]), ([0,1],[0])]:
            with self.assertRaises(ValueError):
                find_crossovers(lambda x: x, grid, values)


if __name__ == '__main__':
    unittest.main()
