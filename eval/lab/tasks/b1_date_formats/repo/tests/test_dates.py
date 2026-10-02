import unittest
from datetime import date

from dateparse.parsing import parse_date
from dateparse.ranges import days_between, in_range


class ParseDateTest(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(parse_date("2024-02-29"), date(2024, 2, 29))

    def test_invalid_iso(self):
        with self.assertRaises(ValueError):
            parse_date("2024-13-01")


class RangeTest(unittest.TestCase):
    def test_days_between(self):
        self.assertEqual(days_between("2024-01-01", "2024-03-01"), 60)

    def test_in_range(self):
        self.assertTrue(in_range("2024-01-15", "2024-01-01", "2024-01-31"))
        self.assertFalse(in_range("2024-02-01", "2024-01-01", "2024-01-31"))


if __name__ == "__main__":
    unittest.main()
