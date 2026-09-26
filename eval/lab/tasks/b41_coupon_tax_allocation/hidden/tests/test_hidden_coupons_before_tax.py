import os
import tempfile
import unittest
from decimal import Decimal

from orders.catalog import default_catalog
from orders.discounts import FixedCoupon, default_coupons
from orders.models import LineItem
from orders.pipeline import OrderService
from orders.pricing import price_lines
from orders.store import OrderStore
from orders.tax import TaxTable, default_tax_table

D = Decimal


class CouponsReduceTaxableAmountTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = OrderStore(os.path.join(self.tmp.name, 'orders.json'))
        self.service = OrderService(default_catalog(), default_coupons(), default_tax_table(), self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_fixed_coupon_is_split_proportionally_before_tax(self):
        record = self.service.place_order('o1', 'c1', 'CA', [('BOOK-1', 1), ('MUG-1', 1), ('LAMP-1', 1)], ['SAVE5'])
        self.assertEqual(record.subtotal, D('55.49'))
        self.assertEqual(record.discount, D('5.00'))
        self.assertEqual(record.line_taxes, {'BOOK-1': D('0.86'), 'MUG-1': D('0.56'), 'LAMP-1': D('2.24')})
        self.assertEqual(record.tax, D('3.66'))
        self.assertEqual(record.total, D('54.15'))

    def test_exempt_lines_still_take_their_share(self):
        record = self.service.place_order('o1', 'c1', 'NY', [('BOOK-1', 2), ('LAMP-1', 1)], ['SAVE5'])
        self.assertEqual(record.line_taxes, {'BOOK-1': D('0.00'), 'LAMP-1': D('2.77')})
        self.assertEqual(record.tax, D('2.77'))
        self.assertEqual(record.total, D('57.75'))

    def test_category_coupon_reduces_tax_on_that_line(self):
        record = self.service.place_order('o1', 'c1', 'CA', [('LAMP-1', 1)], ['HOME20'])
        self.assertEqual(record.discount, D('20.00'))
        self.assertEqual(record.tax, D('1.02'))
        self.assertEqual(record.total, D('15.02'))

    def test_coupons_apply_in_entered_order(self):
        fixed_first = self.service.place_order('o1', 'c1', 'OR', [('LAMP-1', 1)], ['SAVE5', 'TENOFF'])
        self.assertEqual(fixed_first.discount, D('7.90'))
        self.assertEqual(fixed_first.total, D('26.10'))
        percent_first = self.service.place_order('o2', 'c1', 'OR', [('LAMP-1', 1)], ['TENOFF', 'SAVE5'])
        self.assertEqual(percent_first.discount, D('8.40'))
        self.assertEqual(percent_first.total, D('25.60'))

    def test_percent_coupon_is_rounded_per_line(self):
        record = self.service.place_order('o1', 'c1', 'OR', [('BOOK-1', 1), ('TEA-1', 1)], ['TENOFF'])
        self.assertEqual(record.discount, D('1.93'))
        self.assertEqual(record.total, D('17.31'))

    def test_line_taxes_are_persisted(self):
        record = self.service.place_order('o1', 'c1', 'CA', [('BOOK-1', 1), ('TEA-1', 1)], ['SAVE5'])
        self.assertEqual(record.total, D('14.94'))
        loaded = OrderStore(self.store.path).load('o1')
        self.assertEqual(loaded.line_taxes, {'BOOK-1': D('0.70'), 'TEA-1': D('0.00')})
        self.assertEqual(loaded.tax, D('0.70'))


class PriceLinesEdgeCasesTest(unittest.TestCase):
    def test_fixed_coupon_is_capped_at_what_is_left(self):
        lines = [LineItem('A', D('7.50'), 2, 'home')]
        result = price_lines(lines, [FixedCoupon('BIG', D('100.00'))], 'CA', TaxTable({'CA': D('0.0725')}))
        self.assertEqual(result.discount, D('15.00'))
        self.assertEqual(result.tax, D('0.00'))
        self.assertEqual(result.total, D('0.00'))
        self.assertEqual(result.line_taxes, {'A': D('0.00')})

    def test_lines_already_at_zero_take_no_share(self):
        lines = [
            LineItem('A', D('1.00'), 1, 'misc'),
            LineItem('B', D('1.00'), 1, 'misc'),
            LineItem('C', D('1.00'), 1, 'misc'),
            LineItem('D', D('5.00'), 1, 'x'),
        ]
        coupons = [FixedCoupon('XOFF', D('5.00'), category='x'), FixedCoupon('TWO', D('0.02'))]
        result = price_lines(lines, coupons, 'ZZ', TaxTable({'ZZ': D('0.5')}))
        self.assertEqual(result.discount, D('5.02'))
        self.assertEqual(result.line_taxes, {'A': D('0.50'), 'B': D('0.50'), 'C': D('0.50'), 'D': D('0.00')})
        self.assertEqual(result.tax, D('1.50'))
        self.assertEqual(result.total, D('4.48'))


if __name__ == '__main__':
    unittest.main()
