import unittest

from scores import format_lines, podium, rank


class RankTests(unittest.TestCase):
    def test_orders_by_points(self):
        self.assertEqual(rank({'amy': 3, 'bob': 9, 'cat': 5}),
                         [(1, 'bob', 9), (2, 'cat', 5), (3, 'amy', 3)])

    def test_ties_broken_by_name(self):
        self.assertEqual(rank({'bob': 10, 'amy': 10, 'cat': 7}),
                         [(1, 'amy', 10), (2, 'bob', 10), (3, 'cat', 7)])

    def test_empty(self):
        self.assertEqual(rank({}), [])

    def test_podium(self):
        self.assertEqual(podium({'a': 4, 'b': 3, 'c': 2, 'd': 1}), ['a', 'b', 'c'])

    def test_format_lines(self):
        self.assertEqual(format_lines({'amy': 3, 'bob': 9}), ['1. bob (9)', '2. amy (3)'])


if __name__ == '__main__':
    unittest.main()
