import unittest

from stockroom import AuditLog, Inventory


class AddStockTests(unittest.TestCase):
    def test_add_accumulates(self):
        inv = Inventory()
        self.assertEqual(inv.add_stock("APPLE", 3), 3)
        self.assertEqual(inv.add_stock("APPLE", 4), 7)
        self.assertEqual(inv.quantity("APPLE"), 7)
        self.assertEqual(inv.total_units(), 7)

    def test_unknown_sku_has_zero_quantity(self):
        self.assertEqual(Inventory().quantity("NOPE"), 0)

    def test_add_rejects_bad_quantities(self):
        inv = Inventory()
        for bad in (0, -2, 1.5, "3", True):
            with self.subTest(qty=bad):
                with self.assertRaises(ValueError):
                    inv.add_stock("APPLE", bad)
        self.assertEqual(inv.quantity("APPLE"), 0)
        self.assertEqual(len(inv.audit), 0)

    def test_add_many_validates_before_booking(self):
        inv = Inventory()
        with self.assertRaises(ValueError):
            inv.add_many({"APPLE": 2, "PEAR": 0})
        self.assertEqual(inv.snapshot(), {})
        inv.add_many({"APPLE": 2, "PEAR": 5})
        self.assertEqual(inv.snapshot(), {"APPLE": 2, "PEAR": 5})
        self.assertEqual(inv.skus(), ["APPLE", "PEAR"])


class RemoveStockTests(unittest.TestCase):
    def test_remove_reduces_quantity(self):
        inv = Inventory()
        inv.add_stock("PEAR", 10)
        self.assertEqual(inv.remove_stock("PEAR", 4), 6)
        self.assertEqual(inv.quantity("PEAR"), 6)

    def test_remove_rejects_bad_quantities(self):
        inv = Inventory()
        inv.add_stock("PEAR", 5)
        for bad in (0, -1):
            with self.subTest(qty=bad):
                with self.assertRaises(ValueError):
                    inv.remove_stock("PEAR", bad)
        self.assertEqual(inv.quantity("PEAR"), 5)

    def test_movements_are_audited(self):
        log = AuditLog()
        inv = Inventory(audit=log)
        inv.add_stock("PEAR", 5)
        inv.remove_stock("PEAR", 2)
        self.assertEqual(
            [(e.action, e.sku, e.qty) for e in log],
            [("add", "PEAR", 5), ("remove", "PEAR", 2)],
        )
        self.assertEqual(log.net_change("PEAR"), 3)


if __name__ == "__main__":
    unittest.main()
