import unittest

from slug import slugify
from unique import unique_slug


class TestSlugify(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify('Hello, World!'), 'hello-world')
        self.assertEqual(slugify('  multiple   spaces  '), 'multiple-spaces')
        self.assertEqual(slugify('--Already-Slugged--'), 'already-slugged')
        self.assertEqual(slugify('Version 2.0'), 'version-2-0')
        self.assertEqual(slugify('snake_case_name'), 'snake-case-name')

    def test_empty(self):
        self.assertEqual(slugify(''), '')
        self.assertEqual(slugify('!!!'), '')


class TestUniqueSlug(unittest.TestCase):
    def test_no_collision(self):
        self.assertEqual(unique_slug('Hello', set()), 'hello')

    def test_collisions(self):
        self.assertEqual(unique_slug('Hello', {'hello'}), 'hello-2')
        self.assertEqual(unique_slug('Hello', {'hello', 'hello-2'}), 'hello-3')

    def test_fallback(self):
        self.assertEqual(unique_slug('!!!', set()), 'untitled')
        self.assertEqual(unique_slug('???', {'untitled'}), 'untitled-2')


if __name__ == '__main__':
    unittest.main()
