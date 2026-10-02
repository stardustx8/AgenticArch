import unittest

from textkit import slugify


class SlugifyTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify('Hello, World!'), 'hello-world')

    def test_custom_separator(self):
        self.assertEqual(slugify('Release Notes 2024', sep='_'), 'release_notes_2024')

    def test_strips_edges(self):
        self.assertEqual(slugify('  --Draft--  '), 'draft')

    def test_non_ascii_letters_become_separators(self):
        self.assertEqual(slugify('Crème Brûlée'), 'cr-me-br-l-e')


if __name__ == '__main__':
    unittest.main()
