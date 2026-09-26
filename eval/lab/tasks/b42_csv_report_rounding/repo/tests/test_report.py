import unittest
from decimal import Decimal

from reports.fx import MissingRateError, RateTable
from reports.grouping import group_by
from reports.loader import LoadError, load_transactions
from reports.report import build_report, render_report

LINES = [
    'date,region,category,amount,currency',
    '2024-01-02,North,books,10.00,USD',
    '2024-01-03,North,food,"1,000.00",USD',
    '2024-01-03,South,books,20.00,EUR',
    '2024-01-04,South,food,(5.00),USD',
    '2024-01-05,West,services,3.20,GBP',
]


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.rows = load_transactions(LINES)
        self.rates = RateTable('usd', {'EUR': '1.10', 'gbp': 1.25})

    def test_loader_parses_rows(self):
        self.assertEqual(len(self.rows), 5)
        self.assertEqual(self.rows[1].amount, Decimal('1000.00'))
        self.assertEqual(self.rows[3].amount, Decimal('-5.00'))
        self.assertEqual(self.rows[4].currency, 'GBP')
        self.assertEqual(self.rows[0].date.isoformat(), '2024-01-02')

    def test_loader_errors(self):
        with self.assertRaises(LoadError):
            load_transactions(['date,region,amount', '2024-01-01,N,1'])
        with self.assertRaises(LoadError):
            load_transactions(['date,region,category,amount,currency', '2024-01-01,N,x,oops,USD'])
        with self.assertRaises(LoadError):
            load_transactions(['date,region,category,amount,currency', '2024-13-01,N,x,1,USD'])

    def test_group_by(self):
        groups = group_by(self.rows, ['region'])
        self.assertEqual(sorted(groups), [('North',), ('South',), ('West',)])
        self.assertEqual(len(groups[('South',)]), 2)

    def test_build_report_by_region(self):
        report = build_report(self.rows, ['region'], self.rates)
        self.assertEqual(report.currency, 'USD')
        self.assertEqual(
            [(line.group, line.count, line.total) for line in report.lines],
            [
                (('North',), 2, Decimal('1010.00')),
                (('South',), 2, Decimal('17.00')),
                (('West',), 1, Decimal('4.00')),
            ],
        )
        self.assertEqual(report.grand_total, Decimal('1031.00'))

    def test_two_level_grouping(self):
        report = build_report(self.rows, ['region', 'category'], self.rates)
        self.assertEqual(
            [line.group for line in report.lines],
            [('North', 'books'), ('North', 'food'), ('South', 'books'), ('South', 'food'), ('West', 'services')],
        )

    def test_render(self):
        text = render_report(build_report(self.rows, ['region'], self.rates))
        self.assertEqual(text.splitlines(), [
            'region: count, total (USD)',
            'North: 2, USD 1,010.00',
            'South: 2, USD 17.00',
            'West: 1, USD 4.00',
            'TOTAL: 5, USD 1,031.00',
        ])

    def test_missing_rate(self):
        with self.assertRaises(MissingRateError):
            build_report(self.rows, ['region'], RateTable('USD', {'EUR': '1.1'}))
