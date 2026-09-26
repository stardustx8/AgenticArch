import unittest

from textkit import slugify


class SlugifyTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(slugify('Hello, World!'), 'hello-world')

    def test_custom_separator(self):
        self.assertEqual(slugify('Release Notes 2024', sep='_'), 'release_notes_2024')

    def test_strips_edges(self):
        self.assertEqual(slugify('  --Draft--  '), 'draft')

    def test_accented_letters_are_folded(self):
        self.assertEqual(slugify('Crème Brûlée'), 'creme-brulee')


if __name__ == '__main__':
    unittest.main()
