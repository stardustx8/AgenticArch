import unittest
from decimal import Decimal

from reports.fx import RateTable
from reports.loader import load_transactions
from reports.money import round_cents
from reports.report import build_report, render_report
from reports.tax_export import vat_lines

HEADER = 'date,region,category,amount,currency'


def rows(*lines):
    return load_transactions([HEADER, *lines])


class HiddenReportRoundingTest(unittest.TestCase):
    def setUp(self):
        self.rates = RateTable('USD', {'EUR': '0.5', 'JPY': '0.0067'})

    def test_half_up_on_ties_both_signs(self):
        report = build_report(rows(
            '2024-01-01,North,books,0.25,EUR',
            '2024-01-01,South,books,(0.25),EUR',
        ), ['region'], self.rates)
        self.assertEqual(
            [(line.group, line.total) for line in report.lines],
            [(('North',), Decimal('0.13')), (('South',), Decimal('-0.13'))],
        )
        self.assertEqual(render_report(report).splitlines()[1:], [
            'North: 1, USD 0.13',
            'South: 1, USD -0.13',
            'TOTAL: 2, USD 0.00',
        ])

    def test_rounded_once_per_group(self):
        report = build_report(rows(
            '2024-01-01,East,books,0.01,EUR',
            '2024-01-02,East,food,0.01,EUR',
            '2024-01-03,East,food,0.01,EUR',
        ), ['region'], self.rates)
        self.assertEqual(report.lines[0].total, Decimal('0.02'))

    def test_grand_total_is_sum_of_printed_group_totals(self):
        report = build_report(rows(
            '2024-01-01,East,books,0.01,EUR',
            '2024-01-01,West,books,0.01,EUR',
        ), ['region'], self.rates)
        self.assertEqual([line.total for line in report.lines], [Decimal('0.01'), Decimal('0.01')])
        self.assertEqual(report.grand_total, Decimal('0.02'))
        self.assertEqual(render_report(report).splitlines()[-1], 'TOTAL: 2, USD 0.02')

    def test_total_rounding_to_zero_is_not_negative(self):
        report = build_report(rows('2024-01-01,North,books,(0.50),JPY'), ['region'], self.rates)
        self.assertEqual(report.lines[0].total, Decimal('0'))
        text = render_report(report)
        self.assertIn('North: 1, USD 0.00', text.splitlines())
        self.assertNotIn('-0.00', text)


class HiddenTaxExportUnchangedTest(unittest.TestCase):
    def test_vat_still_rounds_half_even(self):
        lines = vat_lines(rows(
            '2024-03-01,North,books,2.50,USD',
            '2024-03-02,North,books,0.50,USD',
            '2024-03-03,North,books,7.50,USD',
        ), RateTable('USD', {}))
        self.assertEqual([str(vat) for _, _, _, vat in lines], ['0.12', '0.02', '0.38'])

    def test_net_still_rounds_half_even(self):
        lines = vat_lines(rows('2024-03-01,North,misc,0.25,EUR'), RateTable('USD', {'EUR': '0.5'}))
        self.assertEqual([(str(net), str(vat)) for _, _, net, vat in lines], [('0.12', '0.00')])

    def test_round_cents_is_still_bankers_rounding(self):
        self.assertEqual(round_cents(Decimal('0.125')), Decimal('0.12'))
        self.assertEqual(round_cents(Decimal('0.135')), Decimal('0.14'))
        self.assertEqual(round_cents(Decimal('-0.125')), Decimal('-0.12'))
