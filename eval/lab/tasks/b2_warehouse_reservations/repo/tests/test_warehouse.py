import unittest

from depot.clock import FakeClock
from depot.errors import OutOfStock
from depot.warehouse import Warehouse


class WarehouseTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(start=50.0)
        self.wh = Warehouse(clock=self.clock)

    def test_movements_are_stamped_with_clock_time(self):
        self.wh.receive("BOLT", 5)
        self.clock.advance(2.5)
        self.wh.ship("BOLT", 1)
        self.assertEqual(
            [(m.kind, m.qty, m.at) for m in self.wh.ledger.movements("BOLT")],
            [("receive", 5, 50.0), ("ship", 1, 52.5)],
        )

    def test_available_tracks_on_hand(self):
        self.wh.receive("BOLT", 5)
        self.wh.ship("BOLT", 2)
        self.assertEqual(self.wh.on_hand("BOLT"), 3)
        self.assertEqual(self.wh.available("BOLT"), 3)
        self.assertEqual(self.wh.available("NUT"), 0)

    def test_ship_out_of_stock(self):
        self.wh.receive("BOLT", 1)
        with self.assertRaises(OutOfStock):
            self.wh.ship("BOLT", 2)
        self.assertEqual(self.wh.on_hand("BOLT"), 1)

    def test_stock_report(self):
        self.wh.receive("BOLT", 4)
        self.wh.receive("NUT", 7)
        self.wh.ship("NUT", 2)
        self.assertEqual(self.wh.stock_report(), {"BOLT": (4, 4), "NUT": (5, 5)})

    def test_fake_clock_never_goes_backwards(self):
        with self.assertRaises(ValueError):
            self.clock.advance(-1.0)
        with self.assertRaises(ValueError):
            self.clock.set(10.0)
        self.assertEqual(self.clock.now(), 50.0)


if __name__ == "__main__":
    unittest.main()
