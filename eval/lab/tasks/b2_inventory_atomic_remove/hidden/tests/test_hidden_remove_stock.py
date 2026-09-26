import unittest

from stockroom import InsufficientStock, Inventory, InventoryError


def _entries(inv):
    return [(e.action, e.sku, e.qty) for e in inv.audit.entries()]


class RemoveStockAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory()
        self.inv.add_stock("APPLE", 5)
        self.inv.add_stock("PEAR", 3)

    def test_over_removal_raises(self):
        with self.assertRaises(InsufficientStock):
            self.inv.remove_stock("APPLE", 6)

    def test_error_attributes(self):
        with self.assertRaises(InsufficientStock) as ctx:
            self.inv.remove_stock("APPLE", 8)
        err = ctx.exception
        self.assertEqual(err.sku, "APPLE")
        self.assertEqual(err.requested, 8)
        self.assertEqual(err.available, 5)

    def test_failed_removal_leaves_stock_and_audit_untouched(self):
        before = _entries(self.inv)
        with self.assertRaises(InsufficientStock):
            self.inv.remove_stock("PEAR", 4)
        self.assertEqual(self.inv.quantity("PEAR"), 3)
        self.assertEqual(self.inv.quantity("APPLE"), 5)
        self.assertEqual(_entries(self.inv), before)
        self.inv.remove_stock("PEAR", 3)
        self.assertEqual(self.inv.quantity("PEAR"), 0)

    def test_removing_exact_quantity_reaches_zero(self):
        self.inv.remove_stock("APPLE", 5)
        self.assertEqual(self.inv.quantity("APPLE"), 0)
        self.assertEqual(_entries(self.inv)[-1], ("remove", "APPLE", 5))
        with self.assertRaises(InsufficientStock) as ctx:
            self.inv.remove_stock("APPLE", 1)
        self.assertEqual(ctx.exception.available, 0)
        self.assertEqual(self.inv.quantity("APPLE"), 0)

    def test_unknown_sku_reports_zero_available(self):
        before = _entries(self.inv)
        with self.assertRaises(InsufficientStock) as ctx:
            self.inv.remove_stock("KIWI", 1)
        self.assertEqual(ctx.exception.sku, "KIWI")
        self.assertEqual(ctx.exception.requested, 1)
        self.assertEqual(ctx.exception.available, 0)
        self.assertEqual(self.inv.quantity("KIWI"), 0)
        self.assertEqual(_entries(self.inv), before)

    def test_is_an_inventory_error(self):
        with self.assertRaises(InventoryError):
            self.inv.remove_stock("APPLE", 99)
        self.assertEqual(self.inv.quantity("APPLE"), 5)


class RemoveManyTests(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory()
        self.inv.add_many({"APPLE": 5, "PEAR": 3, "PLUM": 2})
        self.base_entries = _entries(self.inv)

    def assertUnchanged(self):
        self.assertEqual(self.inv.quantity("APPLE"), 5)
        self.assertEqual(self.inv.quantity("PEAR"), 3)
        self.assertEqual(self.inv.quantity("PLUM"), 2)
        self.assertEqual(_entries(self.inv), self.base_entries)

    def test_removes_every_line(self):
        self.inv.remove_many({"APPLE": 2, "PEAR": 3})
        self.assertEqual(self.inv.quantity("APPLE"), 3)
        self.assertEqual(self.inv.quantity("PEAR"), 0)
        self.assertEqual(self.inv.quantity("PLUM"), 2)

    def test_logs_each_line(self):
        self.inv.remove_many({"APPLE": 2, "PLUM": 1})
        new = _entries(self.inv)[len(self.base_entries):]
        self.assertEqual(sorted(new), [("remove", "APPLE", 2), ("remove", "PLUM", 1)])

    def test_failing_line_rolls_back_everything(self):
        with self.assertRaises(InsufficientStock):
            self.inv.remove_many({"APPLE": 2, "PEAR": 1, "PLUM": 3})
        self.assertUnchanged()

    def test_error_identifies_failing_line(self):
        with self.assertRaises(InsufficientStock) as ctx:
            self.inv.remove_many({"APPLE": 1, "PEAR": 4, "PLUM": 1})
        self.assertEqual(ctx.exception.sku, "PEAR")
        self.assertEqual(ctx.exception.requested, 4)
        self.assertEqual(ctx.exception.available, 3)
        self.assertUnchanged()

    def test_unknown_sku_line_fails_whole_order(self):
        with self.assertRaises(InsufficientStock) as ctx:
            self.inv.remove_many({"APPLE": 1, "KIWI": 2})
        self.assertEqual(ctx.exception.sku, "KIWI")
        self.assertEqual(ctx.exception.available, 0)
        self.assertEqual(self.inv.quantity("KIWI"), 0)
        self.assertUnchanged()

    def test_invalid_quantity_rejected_without_changes(self):
        for bad in (0, -1, 2.0, "1", True):
            with self.subTest(qty=bad):
                with self.assertRaises(ValueError):
                    self.inv.remove_many({"APPLE": 1, "PEAR": bad, "PLUM": 1})
                self.assertUnchanged()

    def test_empty_order_is_a_noop(self):
        self.inv.remove_many({})
        self.assertUnchanged()

    def test_can_empty_stock_exactly(self):
        self.inv.remove_many({"APPLE": 5, "PEAR": 3, "PLUM": 2})
        for sku in ("APPLE", "PEAR", "PLUM"):
            self.assertEqual(self.inv.quantity(sku), 0)
        with self.assertRaises(InsufficientStock):
            self.inv.remove_many({"APPLE": 1})
        self.assertEqual(self.inv.quantity("APPLE"), 0)


if __name__ == "__main__":
    unittest.main()
