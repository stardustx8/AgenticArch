import unittest

from inventory import InventoryService


class CancelHandsUnitsToBackordersTest(unittest.TestCase):
    def setUp(self):
        self.svc = InventoryService(('east', 'west'))

    def test_released_units_go_to_waiting_backorder_first(self):
        self.svc.receive('X', 'east', 3)
        self.svc.reserve('A', 'X', 3)
        self.svc.reserve('B', 'X', 2, allow_backorder=True)
        self.svc.cancel_order('A')
        self.assertEqual(self.svc.reserved('B'), {('X', 'east'): 2})
        self.assertEqual(self.svc.backordered('B'), {})
        self.assertEqual(self.svc.free('X'), 1)
        self.assertEqual(self.svc.free('X', 'east'), 1)

    def test_released_units_follow_fifo_with_partial_fill(self):
        self.svc.receive('X', 'east', 2)
        self.svc.reserve('A', 'X', 2)
        self.svc.reserve('B', 'X', 3, allow_backorder=True)
        self.svc.reserve('C', 'X', 1, allow_backorder=True)
        self.svc.cancel_order('A')
        self.assertEqual(self.svc.reserved('B'), {('X', 'east'): 2})
        self.assertEqual(self.svc.backordered('B'), {'X': 1})
        self.assertEqual(self.svc.reserved('C'), {})
        self.assertEqual(self.svc.backordered('C'), {'X': 1})
        self.assertEqual(self.svc.free('X'), 0)

    def test_cancelled_order_does_not_refill_its_own_backorder(self):
        self.svc.receive('X', 'east', 3)
        self.assertEqual(self.svc.reserve('A', 'X', 5, allow_backorder=True), 3)
        self.svc.reserve('B', 'X', 4, allow_backorder=True)
        self.svc.cancel_order('A')
        self.assertEqual(self.svc.reserved('A'), {})
        self.assertEqual(self.svc.backordered('A'), {})
        self.assertEqual(self.svc.reserved('B'), {('X', 'east'): 3})
        self.assertEqual(self.svc.backordered('B'), {'X': 1})
        self.assertEqual(self.svc.free('X'), 0)

    def test_receipts_after_cancel_skip_the_cancelled_order(self):
        self.svc.reserve('A', 'X', 2, allow_backorder=True)
        self.svc.reserve('B', 'X', 1, allow_backorder=True)
        self.svc.cancel_order('A')
        self.assertEqual(self.svc.backordered('A'), {})
        self.assertEqual(self.svc.receive('X', 'west', 4), [('B', 1)])
        self.assertEqual(self.svc.reserved('A'), {})
        self.assertEqual(self.svc.free('X'), 3)

    def test_units_released_from_several_warehouses(self):
        self.svc.receive('X', 'east', 2)
        self.svc.receive('X', 'west', 1)
        self.svc.reserve('A', 'X', 3)
        self.svc.reserve('B', 'X', 4, allow_backorder=True)
        self.svc.reserve('C', 'X', 5, allow_backorder=True)
        self.svc.cancel_order('A')
        self.assertEqual(sum(self.svc.reserved('B').values()), 3)
        self.assertEqual(self.svc.backordered('B'), {'X': 1})
        self.assertEqual(self.svc.reserved('C'), {})
        self.assertEqual(self.svc.backordered('C'), {'X': 5})
        self.assertEqual(self.svc.free('X'), 0)

    def test_other_skus_are_not_affected(self):
        self.svc.receive('X', 'east', 2)
        self.svc.reserve('A', 'X', 2)
        self.svc.reserve('B', 'Y', 2, allow_backorder=True)
        self.svc.cancel_order('A')
        self.assertEqual(self.svc.free('X'), 2)
        self.assertEqual(self.svc.backordered('B'), {'Y': 2})
        self.assertEqual(self.svc.reserved('B'), {})


if __name__ == '__main__':
    unittest.main()
