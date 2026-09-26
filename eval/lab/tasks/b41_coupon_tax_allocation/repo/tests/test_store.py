import json
import os
import tempfile
import unittest
from decimal import Decimal

from orders.models import LineItem, OrderRecord
from orders.store import DuplicateOrder, OrderNotFound, OrderStore


def make_record(order_id):
    line = LineItem('MUG-1', Decimal('8.50'), 2, 'kitchen')
    return OrderRecord(
        order_id=order_id,
        customer_id='c1',
        region='OR',
        coupons=[],
        lines=[line],
        subtotal=Decimal('17.00'),
        discount=Decimal('0.00'),
        tax=Decimal('0.00'),
        total=Decimal('17.00'),
    )


class OrderStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'orders.json')
        self.store = OrderStore(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip(self):
        self.store.save(make_record('A-1'))
        loaded = OrderStore(self.path).load('A-1')
        self.assertEqual(loaded.total, Decimal('17.00'))
        self.assertEqual(loaded.lines, [LineItem('MUG-1', Decimal('8.50'), 2, 'kitchen')])
        self.assertEqual(loaded.status, 'placed')

    def test_duplicate_ids_rejected(self):
        self.store.save(make_record('A-1'))
        with self.assertRaises(DuplicateOrder):
            self.store.save(make_record('A-1'))

    def test_missing_order(self):
        with self.assertRaises(OrderNotFound):
            self.store.load('nope')

    def test_half_written_entries_are_ignored(self):
        self.store.save(make_record('A-1'))
        with open(self.path, encoding='utf-8') as fh:
            raw = json.load(fh)
        raw['orders'].append({'order_id': 'BROKEN'})
        with open(self.path, 'w', encoding='utf-8') as fh:
            json.dump(raw, fh)
        self.assertEqual(self.store.list_ids(), ['A-1'])
        self.store.save(make_record('A-2'))
        self.assertEqual(self.store.list_ids(), ['A-1', 'A-2'])


if __name__ == '__main__':
    unittest.main()
