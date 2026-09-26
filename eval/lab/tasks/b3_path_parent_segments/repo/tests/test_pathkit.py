import unittest

from pathkit import join, normalize, relative_to


class TestNormalize(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(normalize('/a/./b/../c'), '/a/c')
        self.assertEqual(normalize('a//b/'), 'a/b')
        self.assertEqual(normalize('/../x'), '/x')
        self.assertEqual(normalize('a/..'), '.')
        self.assertEqual(normalize(''), '.')
        self.assertEqual(normalize('/'), '/')


class TestJoin(unittest.TestCase):
    def test_join(self):
        self.assertEqual(join('a', 'b', 'c'), 'a/b/c')
        self.assertEqual(join('a/', 'b'), 'a/b')
        self.assertEqual(join('a', '/b', 'c'), '/b/c')
        self.assertEqual(join('/a/b', '../c'), '/a/c')


class TestRelative(unittest.TestCase):
    def test_relative(self):
        self.assertEqual(relative_to('/a/b/c', '/a/d'), '../b/c')
        self.assertEqual(relative_to('a/b', 'a/b'), '.')
        self.assertEqual(relative_to('/a', '/a/b/c'), '../..')
        self.assertEqual(relative_to('/', '/'), '.')


if __name__ == '__main__':
    unittest.main()
