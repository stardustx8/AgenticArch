import unittest

from inventory import InventoryService, UnknownOrder


class CancelTest(unittest.TestCase):
    def setUp(self):
        self.svc = InventoryService(('east', 'west'))
        self.svc.receive('X', 'east', 5)

    def test_cancel_returns_reserved_units(self):
        self.svc.reserve('A', 'X', 3)
        released = self.svc.cancel_order('A')
        self.assertEqual([(r.sku, r.warehouse, r.qty) for r in released], [('X', 'east', 3)])
        self.assertEqual(self.svc.free('X'), 5)
        self.assertEqual(self.svc.reserved('A'), {})

    def test_cancel_unknown_order(self):
        with self.assertRaises(UnknownOrder):
            self.svc.cancel_order('nope')

    def test_cancel_twice(self):
        self.svc.reserve('A', 'X', 1)
        self.svc.cancel_order('A')
        with self.assertRaises(UnknownOrder):
            self.svc.cancel_order('A')


if __name__ == '__main__':
    unittest.main()
