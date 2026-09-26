import unittest
from datetime import date
from decimal import Decimal

from billing.periods import add_months, days_in_month
from billing.proration import prorate
from billing.schedule import billing_schedule


class PeriodsTest(unittest.TestCase):
    def test_add_months_simple(self):
        self.assertEqual(add_months(date(2024, 1, 15), 1), date(2024, 2, 15))
        self.assertEqual(add_months(date(2024, 11, 10), 3), date(2025, 2, 10))
        self.assertEqual(add_months(date(2024, 3, 10), -3), date(2023, 12, 10))

    def test_days_in_month(self):
        self.assertEqual(days_in_month(2024, 2), 29)
        self.assertEqual(days_in_month(2023, 2), 28)


class ScheduleTest(unittest.TestCase):
    def test_mid_month_anchor(self):
        self.assertEqual(
            billing_schedule(date(2024, 1, 10), 3),
            [
                (date(2024, 1, 10), date(2024, 2, 10)),
                (date(2024, 2, 10), date(2024, 3, 10)),
                (date(2024, 3, 10), date(2024, 4, 10)),
            ],
        )


class ProrationTest(unittest.TestCase):
    def test_half_period(self):
        result = prorate(Decimal("30"), date(2024, 4, 1), date(2024, 5, 1), date(2024, 4, 16))
        self.assertEqual(result, Decimal("15.00"))


if __name__ == "__main__":
    unittest.main()
