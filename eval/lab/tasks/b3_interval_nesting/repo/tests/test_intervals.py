import unittest

from intervals import merge_intervals
from report import gaps, total_covered


class TestIntervals(unittest.TestCase):
    def test_disjoint(self):
        self.assertEqual(merge_intervals([(5, 6), (1, 2)]), [(1, 2), (5, 6)])

    def test_overlap(self):
        self.assertEqual(merge_intervals([(1, 4), (3, 7)]), [(1, 7)])

    def test_touching(self):
        self.assertEqual(merge_intervals([(1, 2), (2, 3)]), [(1, 3)])

    def test_reversed_interval(self):
        with self.assertRaises(ValueError):
            merge_intervals([(3, 1)])

    def test_total_covered(self):
        self.assertEqual(total_covered([(0, 10), (5, 15), (20, 25)]), 20)
        self.assertEqual(total_covered([]), 0)

    def test_gaps(self):
        self.assertEqual(gaps([(2, 4), (6, 8)], 0, 10), [(0, 2), (4, 6), (8, 10)])
        self.assertEqual(gaps([], 0, 5), [(0, 5)])


if __name__ == '__main__':
    unittest.main()
