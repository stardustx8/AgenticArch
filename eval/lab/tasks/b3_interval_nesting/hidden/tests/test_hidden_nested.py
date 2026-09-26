import unittest

from intervals import merge_intervals
from report import gaps, total_covered


class TestNestedIntervals(unittest.TestCase):
    def test_contained_interval_is_absorbed(self):
        self.assertEqual(merge_intervals([(0, 10), (2, 3)]), [(0, 10)])

    def test_contained_then_extended(self):
        self.assertEqual(merge_intervals([(0, 10), (2, 3), (4, 12), (11, 11)]), [(0, 12)])

    def test_same_start_shorter_second(self):
        self.assertEqual(merge_intervals([(1, 9), (1, 3), (5, 6)]), [(1, 9)])

    def test_unsorted_input_with_nesting(self):
        self.assertEqual(merge_intervals([(4, 5), (0, 10), (12, 14), (1, 2)]), [(0, 10), (12, 14)])

    def test_input_not_mutated(self):
        data = [(3, 4), (0, 10)]
        merge_intervals(data)
        self.assertEqual(data, [(3, 4), (0, 10)])

    def test_reversed_interval_still_rejected(self):
        with self.assertRaises(ValueError):
            merge_intervals([(0, 10), (6, 2)])


class TestReportWithNesting(unittest.TestCase):
    def test_total_covered_all_day_block(self):
        self.assertEqual(total_covered([(9, 17), (10, 11), (13, 14)]), 8)

    def test_total_covered_many_nested(self):
        bookings = [(0, 100)] + [(i, i + 1) for i in range(0, 90, 10)]
        self.assertEqual(total_covered(bookings), 100)

    def test_gaps_with_nested_booking(self):
        self.assertEqual(gaps([(9, 17), (10, 11)], 8, 18), [(8, 9), (17, 18)])

    def test_gaps_clipped_window(self):
        self.assertEqual(gaps([(0, 5), (1, 2), (7, 20)], 3, 10), [(5, 7)])

    def test_fully_booked_window(self):
        self.assertEqual(gaps([(0, 24), (3, 4)], 8, 18), [])


if __name__ == '__main__':
    unittest.main()
