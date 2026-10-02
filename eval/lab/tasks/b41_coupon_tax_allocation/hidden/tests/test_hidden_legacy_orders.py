import json
import os
import tempfile
import unittest
from decimal import Decimal

from orders.catalog import default_catalog
from orders.discounts import default_coupons
from orders.pipeline import OrderService
from orders.store import OrderStore
from orders.tax import default_tax_table

LEGACY_ORDER = {
    'order_id': 'OLD-1',
    'customer_id': 'c9',
    'region': 'CA',
    'coupons': [],
    'lines': [{'sku': 'BOOK-1', 'unit_price': '12.99', 'quantity': 1, 'category': 'books'}],
    'subtotal': '12.99',
    'discount': '0.00',
    'tax': '0.94',
    'total': '13.93',
    'status': 'shipped',
}


class LegacyOrdersTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'orders.json')
        with open(self.path, 'w', encoding='utf-8') as fh:
            json.dump({'orders': [LEGACY_ORDER]}, fh)
        self.store = OrderStore(self.path)
        self.service = OrderService(default_catalog(), default_coupons(), default_tax_table(), self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_legacy_order_loads_with_empty_line_taxes(self):
        record = self.store.load('OLD-1')
        self.assertEqual(record.line_taxes, {})
        self.assertEqual(record.total, Decimal('13.93'))
        self.assertEqual(record.status, 'shipped')

    def test_saving_new_orders_keeps_legacy_orders(self):
        new = self.service.place_order('NEW-1', 'c1', 'CA', [('BOOK-1', 1)])
        self.assertEqual(new.line_taxes, {'BOOK-1': Decimal('0.94')})
        self.assertEqual(self.store.list_ids(), ['OLD-1', 'NEW-1'])
        reopened = OrderStore(self.path)
        self.assertEqual(reopened.load('OLD-1').total, Decimal('13.93'))
        self.assertEqual(reopened.load('OLD-1').status, 'shipped')
        self.assertEqual(reopened.load('OLD-1').line_taxes, {})
        self.assertEqual(reopened.load('NEW-1').line_taxes, {'BOOK-1': Decimal('0.94')})

    def test_several_saves_never_drop_legacy_orders(self):
        self.service.place_order('NEW-1', 'c1', 'OR', [('MUG-1', 1)])
        self.service.place_order('NEW-2', 'c1', 'OR', [('LAMP-1', 1)], ['SAVE5'])
        self.assertEqual(OrderStore(self.path).list_ids(), ['OLD-1', 'NEW-1', 'NEW-2'])
        self.assertEqual(self.store.load('NEW-2').line_taxes, {'LAMP-1': Decimal('0.00')})


if __name__ == '__main__':
    unittest.main()
