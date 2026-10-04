import unittest

from pathkit import join, normalize, relative_to


class TestNormalizeParentSegments(unittest.TestCase):
    def test_leading_parent_segments_kept(self):
        cases = {
            '..': '..',
            '../a': '../a',
            '../../a/b': '../../a/b',
            'a/../..': '..',
            'a/../../b': '../b',
            './../.': '..',
            '..//./a/': '../a',
            'a/b/../../../..': '../..',
            '../a/../b': '../b',
            'a/../b/../..': '..',
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(normalize(source), expected)

    def test_absolute_paths_stop_at_root(self):
        self.assertEqual(normalize('/..'), '/')
        self.assertEqual(normalize('/../../a/..'), '/')
        self.assertEqual(normalize('//a/../../b'), '/b')

    def test_normalize_is_idempotent(self):
        for source in ['../a', 'a/../../b', '/../a', '../../', 'x/./y/../../..']:
            with self.subTest(source=source):
                once = normalize(source)
                self.assertEqual(normalize(once), once)


class TestJoinParentSegments(unittest.TestCase):
    def test_join_keeps_unresolvable_parents(self):
        self.assertEqual(join('a', '../../b'), '../b')
        self.assertEqual(join('..', 'x'), '../x')
        self.assertEqual(join('/a', '../../b'), '/b')


class TestRelativeTo(unittest.TestCase):
    def test_from_subdirectory_to_sibling_tree(self):
        self.assertEqual(relative_to('../shared/x', 'app'), '../../shared/x')

    def test_shared_parent_prefix(self):
        self.assertEqual(relative_to('../a', '..'), 'a')
        self.assertEqual(relative_to('../../a', '..'), '../a')
        self.assertEqual(relative_to('../a', '../b'), '../a')
        self.assertEqual(relative_to('..', 'a'), '../..')
        self.assertEqual(relative_to('..', '..'), '.')

    def test_relative_inputs_are_normalized(self):
        self.assertEqual(relative_to('a/b/../c', 'a/./d/'), '../c')
        self.assertEqual(relative_to('x/../../y', '.'), '../y')

    def test_absolute_paths(self):
        self.assertEqual(relative_to('/a/b/../../c', '/x'), '../c')
        self.assertEqual(relative_to('/', '/a/b'), '../..')

    def test_mixing_absolute_and_relative_rejected(self):
        for path, start in [('/a', 'b'), ('a', '/b'), ('/', '.'), ('..', '/')]:
            with self.subTest(path=path, start=start):
                with self.assertRaises(ValueError):
                    relative_to(path, start)

    def test_unknowable_answers_rejected(self):
        for path, start in [('a', '..'), ('.', '..'), ('../a', '../..'), ('a', 'b/../..')]:
            with self.subTest(path=path, start=start):
                with self.assertRaises(ValueError):
                    relative_to(path, start)


if __name__ == '__main__':
    unittest.main()
