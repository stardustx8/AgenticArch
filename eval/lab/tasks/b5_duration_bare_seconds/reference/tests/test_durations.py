import unittest

from timeparse import format_duration, parse_duration


class ParseDurationTests(unittest.TestCase):
    def test_units(self):
        self.assertEqual(parse_duration('45s'), 45)
        self.assertEqual(parse_duration('2m'), 120)
        self.assertEqual(parse_duration('1h30m'), 5400)
        self.assertEqual(parse_duration('2d'), 172800)

    def test_bare_number_means_seconds(self):
        self.assertEqual(parse_duration('90'), 90)
        self.assertEqual(parse_duration(' 5 '), 5)

    def test_invalid(self):
        for bad in ['', '   ', 'abc', '1x', '1h 30m', 'h1']:
            with self.assertRaises(ValueError):
                parse_duration(bad)


class FormatDurationTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_duration(0), '0s')
        self.assertEqual(format_duration(5400), '1h30m')
        self.assertEqual(format_duration(90061), '1d1h1m1s')

    def test_round_trip(self):
        for seconds in [1, 59, 60, 3601, 86400, 100000]:
            self.assertEqual(parse_duration(format_duration(seconds)), seconds)


if __name__ == '__main__':
    unittest.main()
