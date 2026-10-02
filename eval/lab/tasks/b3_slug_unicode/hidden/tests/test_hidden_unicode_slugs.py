import unittest

from slug import slugify
from unique import unique_slug


class TestTransliteration(unittest.TestCase):
    def test_accents(self):
        self.assertEqual(slugify('Crème Brûlée'), 'creme-brulee')
        self.assertEqual(slugify('Ångström units'), 'angstrom-units')
        self.assertEqual(slugify('naïve café'), 'naive-cafe')
        self.assertEqual(slugify('São Paulo'), 'sao-paulo')

    def test_compatibility_forms(self):
        self.assertEqual(slugify('ＡＢＣ　１２３'), 'abc-123')
        self.assertEqual(slugify('ﬁle ﬂow'), 'file-flow')

    def test_untransliterable_characters_are_dropped(self):
        self.assertEqual(slugify('I ❤ Python'), 'i-python')
        self.assertEqual(slugify('日本語'), '')
        self.assertEqual(slugify('Tokyo 東京 2024'), 'tokyo-2024')

    def test_existing_behaviour_kept(self):
        self.assertEqual(slugify('  Hello,   World!  '), 'hello-world')
        self.assertEqual(slugify('--a--b--'), 'a-b')


class TestMaxLength(unittest.TestCase):
    TITLE = 'The Quick Brown Fox'

    def test_no_truncation_needed(self):
        self.assertEqual(slugify(self.TITLE, max_length=19), 'the-quick-brown-fox')
        self.assertEqual(slugify(self.TITLE, max_length=100), 'the-quick-brown-fox')
        self.assertEqual(slugify(self.TITLE), 'the-quick-brown-fox')

    def test_cuts_on_word_boundary(self):
        self.assertEqual(slugify(self.TITLE, max_length=18), 'the-quick-brown')
        self.assertEqual(slugify(self.TITLE, max_length=15), 'the-quick-brown')
        self.assertEqual(slugify(self.TITLE, max_length=14), 'the-quick')
        self.assertEqual(slugify(self.TITLE, max_length=10), 'the-quick')
        self.assertEqual(slugify(self.TITLE, max_length=3), 'the')

    def test_single_long_word_is_hard_cut(self):
        self.assertEqual(slugify(self.TITLE, max_length=2), 'th')
        self.assertEqual(slugify('Supercalifragilistic', max_length=5), 'super')

    def test_truncation_applies_to_transliterated_text(self):
        self.assertEqual(slugify('Crème Brûlée Recipe', max_length=12), 'creme-brulee')

    def test_never_ends_with_hyphen(self):
        full = 'a-bb-ccc-dddd-eeeee'
        for n in range(1, 25):
            with self.subTest(n=n):
                slug = slugify('a bb ccc dddd eeeee', max_length=n)
                self.assertLessEqual(len(slug), n)
                self.assertFalse(slug.endswith('-'))
                self.assertFalse(slug.startswith('-'))
                self.assertTrue(full.startswith(slug))


class TestUniqueWithMaxLength(unittest.TestCase):
    def test_unicode_title_collision(self):
        self.assertEqual(unique_slug('Crème Brûlée', {'creme-brulee'}), 'creme-brulee-2')

    def test_suffix_fits_within_max_length(self):
        existing = {'creme-brulee'}
        slug = unique_slug('Crème Brûlée', existing, max_length=12)
        self.assertLessEqual(len(slug), 12)
        self.assertNotIn(slug, existing)
        self.assertTrue(slug.endswith('-2'))
        self.assertNotIn('--', slug)
        self.assertTrue(slug.startswith('creme'))

    def test_no_collision_respects_max_length(self):
        self.assertEqual(unique_slug('The Quick Brown Fox', set(), max_length=10), 'the-quick')

    def test_repeated_collisions_with_max_length(self):
        existing = set()
        for _ in range(12):
            slug = unique_slug('The Quick Brown Fox', existing, max_length=15)
            self.assertLessEqual(len(slug), 15)
            self.assertNotIn(slug, existing)
            self.assertNotIn('--', slug)
            self.assertFalse(slug.endswith('-'))
            existing.add(slug)
        self.assertIn('the-quick-brown', existing)
        self.assertEqual(len(existing), 12)


if __name__ == '__main__':
    unittest.main()
