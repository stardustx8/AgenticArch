import unittest

from scores import format_lines, podium, rank


class HiddenSharedRankTests(unittest.TestCase):
    def test_shared_rank_then_gap(self):
        self.assertEqual(rank({'bob': 10, 'amy': 10, 'cat': 7}),
                         [(1, 'amy', 10), (1, 'bob', 10), (3, 'cat', 7)])

    def test_multiple_tie_groups(self):
        scores = {'a': 5, 'b': 8, 'c': 5, 'd': 8, 'e': 5, 'f': 1}
        self.assertEqual(rank(scores), [
            (1, 'b', 8), (1, 'd', 8), (3, 'a', 5), (3, 'c', 5), (3, 'e', 5), (6, 'f', 1)])

    def test_all_tied(self):
        self.assertEqual(rank({'y': 0, 'x': 0}), [(1, 'x', 0), (1, 'y', 0)])

    def test_no_ties_unchanged(self):
        self.assertEqual(rank({'amy': 3, 'bob': 9, 'cat': 5}),
                         [(1, 'bob', 9), (2, 'cat', 5), (3, 'amy', 3)])
        self.assertEqual(podium({'a': 4, 'b': 3, 'c': 2, 'd': 1}), ['a', 'b', 'c'])

    def test_podium_includes_ties(self):
        self.assertEqual(podium({'a': 9, 'b': 7, 'c': 7, 'd': 7, 'e': 1}), ['a', 'b', 'c', 'd'])
        self.assertEqual(podium({'a': 9, 'b': 9, 'c': 5, 'd': 5, 'e': 4}), ['a', 'b', 'c', 'd'])

    def test_format_lines_use_shared_rank(self):
        self.assertEqual(format_lines({'amy': 4, 'bob': 4, 'cat': 1}),
                         ['1. amy (4)', '1. bob (4)', '3. cat (1)'])
