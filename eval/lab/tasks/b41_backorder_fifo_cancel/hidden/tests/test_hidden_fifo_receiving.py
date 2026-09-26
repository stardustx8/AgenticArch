import unittest

from inventory import InventoryService


class StrictFifoReceivingTest(unittest.TestCase):
    def setUp(self):
        self.svc = InventoryService(('east', 'west'))

    def test_smaller_later_backorder_does_not_jump_the_queue(self):
        self.svc.reserve('A', 'X', 5, allow_backorder=True)
        self.svc.reserve('B', 'X', 2, allow_backorder=True)
        self.assertEqual(self.svc.receive('X', 'east', 3), [('A', 3)])
        self.assertEqual(self.svc.reserved('A'), {('X', 'east'): 3})
        self.assertEqual(self.svc.backordered('A'), {'X': 2})
        self.assertEqual(self.svc.reserved('B'), {})
        self.assertEqual(self.svc.backordered('B'), {'X': 2})
        self.assertEqual(self.svc.free('X'), 0)

    def test_partially_filled_backorder_keeps_its_place(self):
        self.svc.reserve('A', 'X', 5, allow_backorder=True)
        self.svc.reserve('B', 'X', 2, allow_backorder=True)
        self.svc.receive('X', 'east', 3)
        self.assertEqual(self.svc.receive('X', 'west', 4), [('A', 2), ('B', 2)])
        self.assertEqual(self.svc.reserved('A'), {('X', 'east'): 3, ('X', 'west'): 2})
        self.assertEqual(self.svc.reserved('B'), {('X', 'west'): 2})
        self.assertEqual(self.svc.backordered('A'), {})
        self.assertEqual(self.svc.backordered('B'), {})
        self.assertEqual(self.svc.free('X'), 0)
        self.assertEqual(self.svc.receive('X', 'east', 1), [])
        self.assertEqual(self.svc.free('X'), 1)

    def test_one_receipt_can_fill_several_backorders(self):
        self.svc.reserve('A', 'X', 2, allow_backorder=True)
        self.svc.reserve('B', 'X', 4, allow_backorder=True)
        self.svc.reserve('C', 'X', 1, allow_backorder=True)
        self.assertEqual(self.svc.receive('X', 'east', 5), [('A', 2), ('B', 3)])
        self.assertEqual(self.svc.backordered('B'), {'X': 1})
        self.assertEqual(self.svc.backordered('C'), {'X': 1})
        self.assertEqual(self.svc.reserved('C'), {})
        self.assertEqual(self.svc.free('X'), 0)


if __name__ == '__main__':
    unittest.main()
