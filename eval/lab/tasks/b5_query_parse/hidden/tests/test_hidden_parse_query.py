import unittest

from urlkit import build_query, parse_query


class HiddenParseQueryTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_query('a=1&b=two'), {'a': '1', 'b': 'two'})

    def test_leading_question_mark(self):
        self.assertEqual(parse_query('?page=2'), {'page': '2'})

    def test_empty(self):
        self.assertEqual(parse_query(''), {})
        self.assertEqual(parse_query('?'), {})

    def test_repeated_keys(self):
        self.assertEqual(parse_query('tag=a&x=1&tag=b&tag=c'),
                         {'tag': ['a', 'b', 'c'], 'x': '1'})

    def test_blank_values_kept(self):
        self.assertEqual(parse_query('q=&page=1'), {'q': '', 'page': '1'})
        self.assertEqual(parse_query('tag=&tag=x'), {'tag': ['', 'x']})

    def test_round_trip(self):
        cases = [
            {'q': 'fish & chips', 'lang': 'en'},
            {'q': ''},
            {'tag': ['a', 'b'], 'expr': 'a=b&c', 'plus': '1+1'},
            {'tag': ['', 'x', ''], 'note': 'naïve café'},
            {'path': '/a/b?c#d', 'empty': ''},
        ]
        for params in cases:
            self.assertEqual(parse_query(build_query(params)), params, params)
