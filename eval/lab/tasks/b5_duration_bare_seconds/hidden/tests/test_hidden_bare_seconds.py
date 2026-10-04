import unittest

from timeparse import parse_duration


class HiddenBareSecondsTests(unittest.TestCase):
    def test_bare_number_is_seconds(self):
        self.assertEqual(parse_duration('90'), 90)
        self.assertEqual(parse_duration(' 30 '), 30)
        self.assertEqual(parse_duration('0'), 0)

    def test_bare_matches_seconds_suffix(self):
        for n in [1, 45, 600, 3600]:
            self.assertEqual(parse_duration(str(n)), parse_duration(f'{n}s'))

    def test_suffixed_forms_unchanged(self):
        self.assertEqual(parse_duration('2m'), 120)
        self.assertEqual(parse_duration('1h30m'), 5400)
        self.assertEqual(parse_duration('1d1h1m1s'), 90061)

    def test_errors_unchanged(self):
        for bad in ['', 'abc', '1x', '1h 30m', '-5']:
            with self.assertRaises(ValueError):
                parse_duration(bad)
