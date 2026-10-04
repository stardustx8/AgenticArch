import unittest
from decimal import Decimal

from reports.fx import RateTable
from reports.loader import load_transactions
from reports.report import build_report, render_report

HEADER = 'date,region,category,amount,currency'


def rows(*lines):
    return load_transactions([HEADER, *lines])


class HiddenGroupNormalisationTest(unittest.TestCase):
    def setUp(self):
        self.rates = RateTable('USD', {})

    def test_case_and_whitespace_share_a_group(self):
        report = build_report(rows(
            '2024-01-01, north ,books,1.00,USD',
            '2024-01-02,North,books,2.00,USD',
            '2024-01-03,NORTH,food,3.00,USD',
        ), ['region'], self.rates)
        self.assertEqual(
            [(line.group, line.count, line.total) for line in report.lines],
            [(('north',), 3, Decimal('6.00'))],
        )
        self.assertEqual(report.grand_total, Decimal('6.00'))

    def test_groups_sorted_ignoring_case(self):
        report = build_report(rows(
            '2024-01-01,west,books,1.00,USD',
            '2024-01-01,North,books,1.00,USD',
            '2024-01-01,east,books,1.00,USD',
        ), ['region'], self.rates)
        self.assertEqual([line.group for line in report.lines], [('east',), ('North',), ('west',)])

    def test_every_key_is_normalised(self):
        report = build_report(rows(
            '2024-01-01,South,Books,1.00,USD',
            '2024-01-02,south ,books,1.00,USD',
            '2024-01-03,South,food,1.00,USD',
        ), ['region', 'category'], self.rates)
        self.assertEqual(
            [(line.group, line.count) for line in report.lines],
            [(('South', 'Books'), 2), (('South', 'food'), 1)],
        )

    def test_render_uses_trimmed_label(self):
        text = render_report(build_report(rows('2024-01-01,  East,books,1.00,USD'), ['region'], self.rates))
        self.assertEqual(text.splitlines()[1], 'East: 1, USD 1.00')
