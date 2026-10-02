import unittest
from datetime import date

from dateparse.parsing import parse_date
from dateparse.ranges import days_between, in_range


class EuropeanFormatsTest(unittest.TestCase):
    def test_slash_and_dot(self):
        self.assertEqual(parse_date("31/12/2024"), date(2024, 12, 31))
        self.assertEqual(parse_date("31.12.2024"), date(2024, 12, 31))

    def test_day_first(self):
        self.assertEqual(parse_date("05/03/2024"), date(2024, 3, 5))
        self.assertEqual(parse_date("5/3/2024"), date(2024, 3, 5))
        self.assertEqual(parse_date("5.3.2024"), date(2024, 3, 5))

    def test_leap_day(self):
        self.assertEqual(parse_date("29/02/2024"), date(2024, 2, 29))

    def test_impossible_dates_rejected(self):
        for bad in ("31/02/2024", "29.02.2023", "00/01/2024", "12/13/2024"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_date(bad)


class USFormatsTest(unittest.TestCase):
    def test_abbreviated_month(self):
        self.assertEqual(parse_date("Dec 31, 2024"), date(2024, 12, 31))
        self.assertEqual(parse_date("Mar 5, 2024"), date(2024, 3, 5))
        self.assertEqual(parse_date("Jan 01, 2024"), date(2024, 1, 1))

    def test_full_month(self):
        self.assertEqual(parse_date("December 31, 2024"), date(2024, 12, 31))
        self.assertEqual(parse_date("May 1, 2024"), date(2024, 5, 1))
        self.assertEqual(parse_date("September 9, 2024"), date(2024, 9, 9))

    def test_bad_us_dates(self):
        for bad in ("Foo 5, 2024", "Feb 30, 2024"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_date(bad)


class GeneralTest(unittest.TestCase):
    def test_whitespace_ignored(self):
        self.assertEqual(parse_date("  2024-01-02 \n"), date(2024, 1, 2))
        self.assertEqual(parse_date("\t31/12/2024 "), date(2024, 12, 31))
        self.assertEqual(parse_date(" Dec 31, 2024 "), date(2024, 12, 31))

    def test_garbage_rejected(self):
        for bad in ("", "   ", "yesterday", "2024/12/31", "31/12.2024", "31-12-2024x"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_date(bad)

    def test_ranges_accept_mixed_formats(self):
        self.assertEqual(days_between("31/12/2023", "Jan 1, 2024"), 1)
        self.assertTrue(in_range("15.01.2024", "2024-01-01", "January 31, 2024"))


if __name__ == "__main__":
    unittest.main()
