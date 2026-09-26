import unittest

from pages import page_index, page_label
from roman import from_roman, to_roman


class TestRoman(unittest.TestCase):
    def test_to_roman(self):
        self.assertEqual(to_roman(1994), 'MCMXCIV')
        self.assertEqual(to_roman(3999), 'MMMCMXCIX')
        self.assertEqual(to_roman(4), 'IV')
        self.assertEqual(to_roman(40), 'XL')

    def test_to_roman_range(self):
        for n in (0, -1, 4000):
            with self.assertRaises(ValueError):
                to_roman(n)

    def test_from_roman(self):
        self.assertEqual(from_roman('MCMXCIV'), 1994)
        self.assertEqual(from_roman('xiv'), 14)

    def test_from_roman_bad_symbol(self):
        with self.assertRaises(ValueError):
            from_roman('XIZ')


class TestPages(unittest.TestCase):
    def test_labels(self):
        self.assertEqual([page_label(i, 3) for i in range(1, 6)], ['i', 'ii', 'iii', '1', '2'])

    def test_index(self):
        self.assertEqual(page_index('ii', 5), 2)
        self.assertEqual(page_index('3', 5), 8)

    def test_index_beyond_front_matter(self):
        with self.assertRaises(ValueError):
            page_index('ix', 5)


if __name__ == '__main__':
    unittest.main()
