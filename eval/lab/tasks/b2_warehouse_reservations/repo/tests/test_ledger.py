import unittest

from depot.errors import DepotError, OutOfStock
from depot.stock import StockLedger


class StockLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = StockLedger()

    def test_receive_and_ship(self):
        self.ledger.receive("BOLT", 10, at=1.0)
        self.assertEqual(self.ledger.ship("BOLT", 4, at=2.0), 6)
        self.assertEqual(self.ledger.on_hand("BOLT"), 6)
        self.assertEqual(self.ledger.on_hand("NUT"), 0)

    def test_ship_more_than_on_hand(self):
        self.ledger.receive("BOLT", 2, at=1.0)
        with self.assertRaises(OutOfStock) as ctx:
            self.ledger.ship("BOLT", 3, at=2.0)
        err = ctx.exception
        self.assertIsInstance(err, DepotError)
        self.assertEqual((err.sku, err.requested, err.available), ("BOLT", 3, 2))
        self.assertEqual(self.ledger.on_hand("BOLT"), 2)

    def test_quantities_must_be_positive_ints(self):
        for bad in (0, -1, 1.5, True):
            with self.subTest(qty=bad):
                with self.assertRaises(ValueError):
                    self.ledger.receive("BOLT", bad, at=0.0)
        self.assertEqual(self.ledger.movements(), [])

    def test_movements_filtered_by_sku(self):
        self.ledger.receive("BOLT", 3, at=1.0)
        self.ledger.receive("NUT", 8, at=1.5)
        self.ledger.ship("BOLT", 1, at=2.0)
        self.assertEqual(
            [(m.kind, m.qty, m.at) for m in self.ledger.movements("BOLT")],
            [("receive", 3, 1.0), ("ship", 1, 2.0)],
        )
        self.assertEqual(len(self.ledger.movements()), 3)
        self.assertEqual(self.ledger.skus(), ["BOLT", "NUT"])


if __name__ == "__main__":
    unittest.main()
