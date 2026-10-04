import unittest

from pages import page_index, page_label
from roman import from_roman, to_roman

NON_CANONICAL = [
    'IIII', 'VV', 'VX', 'IC', 'IL', 'XM', 'IIX', 'XXXX', 'LL', 'DD', 'MMMM',
    'IXI', 'XCX', 'CMCM', 'IVI', 'VIV', 'XIIII', 'CCCC', 'LXL', 'MCMC',
]


class TestStrictFromRoman(unittest.TestCase):
    def test_round_trip_every_value(self):
        for n in range(1, 4000):
            numeral = to_roman(n)
            self.assertEqual(from_roman(numeral), n)
            self.assertEqual(from_roman(numeral.lower()), n)

    def test_mixed_case_is_fine(self):
        self.assertEqual(from_roman('xIv'), 14)
        self.assertEqual(from_roman('McMxCiV'), 1994)

    def test_rejects_non_canonical(self):
        for text in NON_CANONICAL:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    from_roman(text)
                with self.assertRaises(ValueError):
                    from_roman(text.lower())

    def test_rejects_empty_and_junk(self):
        for text in ['', ' ', 'X I', 'XIV ', 'ABC', '0', '-X']:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    from_roman(text)


class TestStrictPageIndex(unittest.TestCase):
    def test_non_canonical_page_labels_rejected(self):
        for label in ['iiii', 'ic', 'vv', '']:
            with self.subTest(label=label):
                with self.assertRaises(ValueError):
                    page_index(label, 200)

    def test_round_trip_page_labels(self):
        for i in range(1, 60):
            self.assertEqual(page_index(page_label(i, 40), 40), i)


if __name__ == '__main__':
    unittest.main()
