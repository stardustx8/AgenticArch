import unittest

from textkit import slugify


class HiddenSlugFoldTests(unittest.TestCase):
    def test_accents_are_folded(self):
        self.assertEqual(slugify('Crème Brûlée'), 'creme-brulee')
        self.assertEqual(slugify('Ångström units'), 'angstrom-units')
        self.assertEqual(slugify('Façade São Paulo'), 'facade-sao-paulo')

    def test_folding_with_custom_separator(self):
        self.assertEqual(slugify('Naïve Café', sep='_'), 'naive_cafe')

    def test_unfoldable_characters_still_separate(self):
        self.assertEqual(slugify('a日b'), 'a-b')
        self.assertEqual(slugify('tokyo 東京 guide'), 'tokyo-guide')

    def test_plain_ascii_unchanged(self):
        self.assertEqual(slugify('Hello, World!'), 'hello-world')
        self.assertEqual(slugify('  --Draft--  '), 'draft')
        self.assertEqual(slugify('Release Notes 2024', sep='_'), 'release_notes_2024')
