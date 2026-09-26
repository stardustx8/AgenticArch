import unittest

from urlkit import build_query


class BuildQueryTests(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(build_query({'a': 1, 'b': 'two'}), 'a=1&b=two')

    def test_escaping(self):
        self.assertEqual(build_query({'q': 'fish & chips'}), 'q=fish%20%26%20chips')

    def test_lists(self):
        self.assertEqual(build_query({'tag': ['x', 'y']}), 'tag=x&tag=y')

    def test_blank(self):
        self.assertEqual(build_query({'q': ''}), 'q=')


if __name__ == '__main__':
    unittest.main()
