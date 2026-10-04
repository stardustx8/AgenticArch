import unittest

from inventory import InsufficientStock, InvalidQuantity, InventoryService


class AllocationTest(unittest.TestCase):
    def setUp(self):
        self.svc = InventoryService(('east', 'west'))
        self.svc.receive('X', 'east', 3)
        self.svc.receive('X', 'west', 4)

    def test_reserve_uses_warehouses_in_priority_order(self):
        self.assertEqual(self.svc.reserve('A', 'X', 5), 5)
        self.assertEqual(self.svc.reserved('A'), {('X', 'east'): 3, ('X', 'west'): 2})
        self.assertEqual(self.svc.free('X'), 2)
        self.assertEqual(self.svc.free('X', 'east'), 0)

    def test_insufficient_stock_without_backorder(self):
        with self.assertRaises(InsufficientStock):
            self.svc.reserve('A', 'X', 8)
        self.assertEqual(self.svc.free('X'), 7)
        self.assertEqual(self.svc.reserved('A'), {})

    def test_backorder_for_shortfall(self):
        self.assertEqual(self.svc.reserve('A', 'X', 10, allow_backorder=True), 7)
        self.assertEqual(self.svc.backordered('A'), {'X': 3})
        self.assertEqual(self.svc.free('X'), 0)

    def test_rejects_non_positive_quantity(self):
        with self.assertRaises(InvalidQuantity):
            self.svc.reserve('A', 'X', 0)


if __name__ == '__main__':
    unittest.main()
