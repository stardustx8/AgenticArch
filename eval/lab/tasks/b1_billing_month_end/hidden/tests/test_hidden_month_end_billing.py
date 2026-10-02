import unittest
from datetime import date
from decimal import Decimal

from billing.periods import add_months
from billing.proration import prorate
from billing.schedule import billing_schedule, current_period


class AddMonthsClampTest(unittest.TestCase):
    def test_clamps_to_month_end(self):
        self.assertEqual(add_months(date(2024, 1, 31), 1), date(2024, 2, 29))
        self.assertEqual(add_months(date(2023, 1, 31), 1), date(2023, 2, 28))
        self.assertEqual(add_months(date(2024, 1, 30), 1), date(2024, 2, 29))
        self.assertEqual(add_months(date(2024, 3, 31), 1), date(2024, 4, 30))

    def test_negative_and_year_crossing(self):
        self.assertEqual(add_months(date(2024, 3, 31), -1), date(2024, 2, 29))
        self.assertEqual(add_months(date(2024, 1, 31), -2), date(2023, 11, 30))
        self.assertEqual(add_months(date(2024, 12, 31), 2), date(2025, 2, 28))

    def test_leap_day_yearly(self):
        self.assertEqual(add_months(date(2024, 2, 29), 12), date(2025, 2, 28))
        self.assertEqual(add_months(date(2024, 2, 29), 48), date(2028, 2, 29))

    def test_zero(self):
        self.assertEqual(add_months(date(2024, 1, 31), 0), date(2024, 1, 31))


class ScheduleAnchorTest(unittest.TestCase):
    def test_month_end_anchor_returns_to_31st(self):
        self.assertEqual(
            billing_schedule(date(2024, 1, 31), 4),
            [
                (date(2024, 1, 31), date(2024, 2, 29)),
                (date(2024, 2, 29), date(2024, 3, 31)),
                (date(2024, 3, 31), date(2024, 4, 30)),
                (date(2024, 4, 30), date(2024, 5, 31)),
            ],
        )

    def test_anchor_30th(self):
        periods = billing_schedule(date(2023, 12, 30), 3)
        self.assertEqual([p[1] for p in periods], [date(2024, 1, 30), date(2024, 2, 29), date(2024, 3, 30)])

    def test_leap_day_anchor(self):
        periods = billing_schedule(date(2024, 2, 29), 13)
        self.assertEqual(periods[1], (date(2024, 3, 29), date(2024, 4, 29)))
        self.assertEqual(periods[11], (date(2025, 1, 29), date(2025, 2, 28)))
        self.assertEqual(periods[12], (date(2025, 2, 28), date(2025, 3, 29)))

    def test_periods_are_contiguous(self):
        periods = billing_schedule(date(2024, 1, 31), 24)
        self.assertEqual(len(periods), 24)
        for (s1, e1), (s2, _) in zip(periods, periods[1:]):
            self.assertEqual(e1, s2)
            self.assertLess(s1, e1)

    def test_zero_count(self):
        self.assertEqual(billing_schedule(date(2024, 1, 31), 0), [])


class CurrentPeriodTest(unittest.TestCase):
    ANCHOR = date(2024, 1, 31)

    def test_inside_short_month_period(self):
        self.assertEqual(current_period(self.ANCHOR, date(2024, 3, 15)), (date(2024, 2, 29), date(2024, 3, 31)))

    def test_boundaries(self):
        self.assertEqual(current_period(self.ANCHOR, date(2024, 1, 31)), (date(2024, 1, 31), date(2024, 2, 29)))
        self.assertEqual(current_period(self.ANCHOR, date(2024, 2, 28)), (date(2024, 1, 31), date(2024, 2, 29)))
        self.assertEqual(current_period(self.ANCHOR, date(2024, 2, 29)), (date(2024, 2, 29), date(2024, 3, 31)))
        self.assertEqual(current_period(self.ANCHOR, date(2024, 3, 31)), (date(2024, 3, 31), date(2024, 4, 30)))

    def test_far_future(self):
        self.assertEqual(current_period(self.ANCHOR, date(2026, 3, 1)), (date(2026, 2, 28), date(2026, 3, 31)))

    def test_mid_month_anchor(self):
        self.assertEqual(current_period(date(2024, 1, 10), date(2024, 3, 9)), (date(2024, 2, 10), date(2024, 3, 10)))

    def test_before_anchor_raises(self):
        with self.assertRaises(ValueError):
            current_period(self.ANCHOR, date(2024, 1, 30))


class ProrationEdgeTest(unittest.TestCase):
    START, END = date(2024, 4, 1), date(2024, 5, 1)  # 30 days

    def test_rounds_half_up(self):
        # 10.01 * 15 / 30 = 5.005
        self.assertEqual(prorate(Decimal("10.01"), self.START, self.END, date(2024, 4, 16)), Decimal("5.01"))

    def test_change_on_or_after_end_is_zero(self):
        for change in (date(2024, 5, 1), date(2024, 6, 15)):
            with self.subTest(change=change):
                self.assertEqual(str(prorate(Decimal("30"), self.START, self.END, change)), "0.00")

    def test_change_on_or_before_start_is_full(self):
        for change in (date(2024, 4, 1), date(2024, 3, 1)):
            with self.subTest(change=change):
                self.assertEqual(str(prorate(Decimal("30"), self.START, self.END, change)), "30.00")

    def test_accepts_str_int_float(self):
        self.assertEqual(prorate("19.99", self.START, self.END, date(2024, 4, 1)), Decimal("19.99"))
        self.assertEqual(prorate(60, self.START, self.END, date(2024, 4, 21)), Decimal("20.00"))
        self.assertEqual(prorate(0.3, self.START, self.END, date(2024, 4, 16)), Decimal("0.15"))

    def test_with_schedule_period(self):
        start, end = billing_schedule(date(2024, 1, 31), 2)[1]  # Feb 29 -> Mar 31, 31 days
        self.assertEqual(prorate(Decimal("31.00"), start, end, date(2024, 3, 21)), Decimal("10.00"))


if __name__ == "__main__":
    unittest.main()
