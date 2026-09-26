import datetime
import unittest

from bizdays import add_business_days, business_days_between
from calendars import BusinessCalendar

D = datetime.date


class TestBizDays(unittest.TestCase):
    def test_friday_plus_one(self):
        self.assertEqual(add_business_days(D(2024, 1, 5), 1), D(2024, 1, 8))

    def test_zero(self):
        self.assertEqual(add_business_days(D(2024, 1, 6), 0), D(2024, 1, 6))

    def test_holiday_skipped(self):
        cal = BusinessCalendar([D(2024, 1, 8)])
        self.assertEqual(add_business_days(D(2024, 1, 5), 1, cal), D(2024, 1, 9))

    def test_between(self):
        self.assertEqual(business_days_between(D(2024, 1, 1), D(2024, 1, 8)), 5)
        self.assertEqual(business_days_between(D(2024, 1, 5), D(2024, 1, 5)), 0)

    def test_add_holiday(self):
        cal = BusinessCalendar()
        cal.add_holiday(D(2024, 1, 2))
        self.assertFalse(cal.is_business_day(D(2024, 1, 2)))
        self.assertTrue(cal.is_business_day(D(2024, 1, 3)))
        self.assertFalse(cal.is_business_day(D(2024, 1, 6)))


if __name__ == '__main__':
    unittest.main()
