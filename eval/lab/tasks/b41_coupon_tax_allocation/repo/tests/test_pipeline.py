import os
import tempfile
import unittest
from decimal import Decimal

from orders.catalog import UnknownProduct, default_catalog
from orders.discounts import UnknownCoupon, default_coupons
from orders.pipeline import EmptyOrder, OrderService
from orders.store import OrderStore
from orders.tax import default_tax_table


class OrderServiceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = OrderStore(os.path.join(self.tmp.name, 'orders.json'))
        self.service = OrderService(default_catalog(), default_coupons(), default_tax_table(), self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_tax_is_per_line_and_skips_exempt_categories(self):
        record = self.service.place_order('o1', 'c1', 'CA', [('BOOK-1', 1), ('TEA-1', 2)])
        self.assertEqual(record.subtotal, Decimal('25.49'))
        self.assertEqual(record.tax, Decimal('0.94'))
        self.assertEqual(record.total, Decimal('26.43'))

    def test_category_coupon_only_discounts_its_category(self):
        record = self.service.place_order('o1', 'c1', 'OR', [('LAMP-1', 1), ('BOOK-1', 1)], ['HOME20'])
        self.assertEqual(record.discount, Decimal('20.00'))
        self.assertEqual(record.total, Decimal('26.99'))

    def test_coupon_without_eligible_lines_gives_nothing(self):
        record = self.service.place_order('o1', 'c1', 'OR', [('BOOK-1', 1)], ['HOME20'])
        self.assertEqual(record.discount, Decimal('0.00'))
        self.assertEqual(record.total, Decimal('12.99'))

    def test_repeated_coupon_codes_count_once(self):
        record = self.service.place_order('o1', 'c1', 'OR', [('LAMP-1', 1)], ['tenoff', ' TENOFF '])
        self.assertEqual(record.coupons, ['TENOFF'])
        self.assertEqual(record.discount, Decimal('3.40'))

    def test_duplicate_skus_are_merged(self):
        record = self.service.place_order('o1', 'c1', 'OR', [('MUG-1', 1), ('MUG-1', 2)])
        self.assertEqual(len(record.lines), 1)
        self.assertEqual(record.lines[0].quantity, 3)
        self.assertEqual(record.subtotal, Decimal('25.50'))

    def test_placed_order_is_persisted(self):
        record = self.service.place_order('o1', 'c1', 'CA', [('MUG-1', 1)])
        self.assertEqual(self.store.load('o1').total, record.total)

    def test_rejects_bad_input(self):
        with self.assertRaises(EmptyOrder):
            self.service.place_order('o1', 'c1', 'CA', [])
        with self.assertRaises(ValueError):
            self.service.place_order('o2', 'c1', 'CA', [('MUG-1', 0)])
        with self.assertRaises(UnknownProduct):
            self.service.place_order('o3', 'c1', 'CA', [('NOPE', 1)])
        with self.assertRaises(UnknownCoupon):
            self.service.place_order('o4', 'c1', 'CA', [('MUG-1', 1)], ['BOGUS'])
        self.assertEqual(self.store.list_ids(), [])


if __name__ == '__main__':
    unittest.main()
