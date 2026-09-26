import unittest

from inventory import InventoryService


class ReceivingTest(unittest.TestCase):
    def setUp(self):
        self.svc = InventoryService(('east', 'west'))

    def test_receive_without_backorders_adds_free_stock(self):
        self.assertEqual(self.svc.receive('X', 'east', 4), [])
        self.assertEqual(self.svc.free('X'), 4)

    def test_receive_fills_backorder_completely(self):
        self.svc.reserve('A', 'X', 2, allow_backorder=True)
        self.assertEqual(self.svc.receive('X', 'west', 5), [('A', 2)])
        self.assertEqual(self.svc.backordered('A'), {})
        self.assertEqual(self.svc.reserved('A'), {('X', 'west'): 2})
        self.assertEqual(self.svc.free('X', 'west'), 3)

    def test_receive_only_touches_same_sku(self):
        self.svc.reserve('A', 'Y', 2, allow_backorder=True)
        self.assertEqual(self.svc.receive('X', 'east', 5), [])
        self.assertEqual(self.svc.backordered('A'), {'Y': 2})

    def test_receiving_skips_backorder_that_cannot_be_fully_filled(self):
        self.svc.reserve('A', 'X', 5, allow_backorder=True)
        self.svc.reserve('B', 'X', 2, allow_backorder=True)
        self.assertEqual(self.svc.receive('X', 'east', 3), [('B', 2)])
        self.assertEqual(self.svc.backordered('A'), {'X': 5})
        self.assertEqual(self.svc.backordered('B'), {})
        self.assertEqual(self.svc.free('X'), 1)


if __name__ == '__main__':
    unittest.main()
