import datetime
import unittest

from bizdays import add_business_days, business_days_between
from calendars import BusinessCalendar

D = datetime.date


def sign(x):
    return (x > 0) - (x < 0)


class TestBackwards(unittest.TestCase):
    def test_monday_minus_one_is_friday(self):
        self.assertEqual(add_business_days(D(2024, 1, 8), -1), D(2024, 1, 5))

    def test_weekend_start_minus_one(self):
        self.assertEqual(add_business_days(D(2024, 1, 6), -1), D(2024, 1, 5))
        self.assertEqual(add_business_days(D(2024, 1, 7), -1), D(2024, 1, 5))

    def test_forward_from_weekend_unchanged(self):
        self.assertEqual(add_business_days(D(2024, 1, 6), 1), D(2024, 1, 8))

    def test_full_week_back(self):
        self.assertEqual(add_business_days(D(2024, 1, 8), -5), D(2024, 1, 1))

    def test_holidays_skipped_backwards(self):
        cal = BusinessCalendar([D(2024, 1, 1), D(2024, 1, 5)])
        self.assertEqual(add_business_days(D(2024, 1, 8), -1, cal), D(2024, 1, 4))
        self.assertEqual(add_business_days(D(2024, 1, 8), -4, cal), D(2023, 12, 29))

    def test_zero_is_identity_even_on_weekend(self):
        self.assertEqual(add_business_days(D(2024, 1, 6), 0), D(2024, 1, 6))

    def test_crosses_year_boundary(self):
        self.assertEqual(add_business_days(D(2024, 1, 2), -2), D(2023, 12, 29))


class TestNegativeBetween(unittest.TestCase):
    def test_simple_negative(self):
        self.assertEqual(business_days_between(D(2024, 1, 8), D(2024, 1, 5)), -1)
        self.assertEqual(business_days_between(D(2024, 1, 8), D(2024, 1, 1)), -5)

    def test_same_day(self):
        self.assertEqual(business_days_between(D(2024, 1, 6), D(2024, 1, 6)), 0)

    def test_round_trip_property(self):
        cal = BusinessCalendar([D(2024, 2, 12), D(2024, 2, 14), D(2024, 2, 19)])
        days = [D(2024, 2, 1) + datetime.timedelta(days=i) for i in range(35)]
        for start in days:
            for end in days:
                if not cal.is_business_day(end):
                    continue
                n = business_days_between(start, end, cal)
                self.assertEqual(add_business_days(start, n, cal), end, (start, end, n))
                self.assertEqual(sign(n), sign((end - start).days), (start, end, n))

    def test_antisymmetric_for_business_days(self):
        cal = BusinessCalendar([D(2024, 2, 14)])
        all_days = [D(2024, 2, 1) + datetime.timedelta(days=i) for i in range(30)]
        days = [d for d in all_days if cal.is_business_day(d)]
        for a in days:
            for b in days:
                self.assertEqual(
                    business_days_between(a, b, cal),
                    -business_days_between(b, a, cal),
                    (a, b),
                )


if __name__ == '__main__':
    unittest.main()
