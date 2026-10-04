import unittest

from depot import errors
from depot.clock import FakeClock
from depot.errors import OutOfStock
from depot.warehouse import Warehouse


class ReservationTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock(start=100.0)
        self.wh = Warehouse(clock=self.clock)
        self.wh.receive("WIDGET", 10)
        self.wh.receive("GADGET", 5)

    def assertStock(self, sku, on_hand, available):
        self.assertEqual(self.wh.on_hand(sku), on_hand, f"on_hand({sku})")
        self.assertEqual(self.wh.available(sku), available, f"available({sku})")


class ReserveTests(ReservationTestCase):
    def test_reserve_holds_stock_without_touching_on_hand(self):
        self.wh.reserve("o-1", {"WIDGET": 4}, ttl=30.0)
        self.assertStock("WIDGET", 10, 6)
        self.assertStock("GADGET", 5, 5)

    def test_reserve_multiple_lines(self):
        self.wh.reserve("o-1", {"WIDGET": 3, "GADGET": 5}, ttl=30.0)
        self.assertStock("WIDGET", 10, 7)
        self.assertStock("GADGET", 5, 0)

    def test_insufficient_line_holds_nothing(self):
        with self.assertRaises(OutOfStock):
            self.wh.reserve("o-1", {"WIDGET": 3, "GADGET": 6}, ttl=30.0)
        self.assertStock("WIDGET", 10, 10)
        self.assertStock("GADGET", 5, 5)
        with self.assertRaises(errors.ReservationError):
            self.wh.commit("o-1")
        self.assertStock("WIDGET", 10, 10)
        self.wh.reserve("o-1", {"WIDGET": 3, "GADGET": 5}, ttl=30.0)
        self.assertStock("WIDGET", 10, 7)
        self.assertStock("GADGET", 5, 0)

    def test_unknown_sku_is_out_of_stock(self):
        with self.assertRaises(OutOfStock):
            self.wh.reserve("o-1", {"WIDGET": 1, "SPROCKET": 1}, ttl=30.0)
        self.assertStock("WIDGET", 10, 10)

    def test_duplicate_active_order_id_rejected(self):
        self.wh.reserve("o-1", {"WIDGET": 2}, ttl=30.0)
        with self.assertRaises(errors.ReservationError):
            self.wh.reserve("o-1", {"WIDGET": 1}, ttl=30.0)
        self.assertStock("WIDGET", 10, 8)
        self.wh.commit("o-1")
        self.assertStock("WIDGET", 8, 8)

    def test_non_positive_ttl_rejected(self):
        for ttl in (0, 0.0, -5.0):
            with self.subTest(ttl=ttl):
                with self.assertRaises(ValueError):
                    self.wh.reserve("o-1", {"WIDGET": 1}, ttl=ttl)
                self.assertStock("WIDGET", 10, 10)

    def test_non_positive_line_quantity_rejected(self):
        for qty in (0, -2):
            with self.subTest(qty=qty):
                with self.assertRaises(ValueError):
                    self.wh.reserve("o-1", {"WIDGET": 1, "GADGET": qty}, ttl=30.0)
                self.assertStock("WIDGET", 10, 10)
                self.assertStock("GADGET", 5, 5)

    def test_two_orders_share_a_sku(self):
        self.wh.reserve("o-1", {"WIDGET": 6}, ttl=30.0)
        self.wh.reserve("o-2", {"WIDGET": 4}, ttl=30.0)
        self.assertStock("WIDGET", 10, 0)
        with self.assertRaises(OutOfStock):
            self.wh.reserve("o-3", {"WIDGET": 1}, ttl=30.0)
        self.wh.release("o-1")
        self.assertStock("WIDGET", 10, 6)
        self.wh.commit("o-2")
        self.assertStock("WIDGET", 6, 6)


class CommitReleaseTests(ReservationTestCase):
    def test_commit_deducts_on_hand(self):
        self.wh.reserve("o-1", {"WIDGET": 4, "GADGET": 2}, ttl=30.0)
        self.clock.advance(10.0)
        self.wh.commit("o-1")
        self.assertStock("WIDGET", 6, 6)
        self.assertStock("GADGET", 3, 3)

    def test_commit_twice_raises(self):
        self.wh.reserve("o-1", {"WIDGET": 4}, ttl=30.0)
        self.wh.commit("o-1")
        with self.assertRaises(errors.ReservationError):
            self.wh.commit("o-1")
        self.assertStock("WIDGET", 6, 6)

    def test_release_returns_stock_and_frees_order_id(self):
        self.wh.reserve("o-1", {"WIDGET": 4}, ttl=30.0)
        self.wh.release("o-1")
        self.assertStock("WIDGET", 10, 10)
        with self.assertRaises(errors.ReservationError):
            self.wh.release("o-1")
        self.wh.reserve("o-1", {"WIDGET": 7}, ttl=30.0)
        self.assertStock("WIDGET", 10, 3)

    def test_unknown_order_id(self):
        with self.assertRaises(errors.ReservationError):
            self.wh.commit("nope")
        with self.assertRaises(errors.ReservationError):
            self.wh.release("nope")
        self.assertStock("WIDGET", 10, 10)


class ExpiryTests(ReservationTestCase):
    def test_hold_active_until_just_before_deadline(self):
        self.wh.reserve("o-1", {"WIDGET": 4}, ttl=2.5)
        self.clock.set(102.25)
        self.assertStock("WIDGET", 10, 6)
        self.wh.commit("o-1")
        self.assertStock("WIDGET", 6, 6)

    def test_hold_expires_exactly_at_deadline(self):
        self.wh.reserve("o-1", {"WIDGET": 4}, ttl=2.5)
        self.clock.set(102.5)
        self.assertStock("WIDGET", 10, 10)

    def test_commit_after_expiry_raises_and_does_not_deduct(self):
        self.wh.reserve("o-1", {"WIDGET": 4}, ttl=2.5)
        self.clock.set(102.5)
        with self.assertRaises(errors.ReservationExpired) as ctx:
            self.wh.commit("o-1")
        self.assertIsInstance(ctx.exception, errors.ReservationError)
        self.assertStock("WIDGET", 10, 10)

    def test_order_id_reusable_after_expiry(self):
        self.wh.reserve("o-1", {"WIDGET": 4}, ttl=2.5)
        self.clock.advance(3.0)
        self.wh.reserve("o-1", {"WIDGET": 6}, ttl=30.0)
        self.assertStock("WIDGET", 10, 4)
        self.wh.commit("o-1")
        self.assertStock("WIDGET", 4, 4)

    def test_expired_hold_frees_stock_for_other_orders(self):
        self.wh.reserve("o-1", {"WIDGET": 10}, ttl=2.5)
        with self.assertRaises(OutOfStock):
            self.wh.reserve("o-2", {"WIDGET": 1}, ttl=2.5)
        self.clock.advance(2.5)
        self.wh.reserve("o-2", {"WIDGET": 10}, ttl=30.0)
        self.assertStock("WIDGET", 10, 0)


class ShipWithHoldsTests(ReservationTestCase):
    def test_ship_cannot_take_held_stock(self):
        self.wh.reserve("o-1", {"WIDGET": 8}, ttl=30.0)
        with self.assertRaises(OutOfStock):
            self.wh.ship("WIDGET", 3)
        self.assertStock("WIDGET", 10, 2)
        self.wh.ship("WIDGET", 2)
        self.assertStock("WIDGET", 8, 0)
        self.wh.commit("o-1")
        self.assertStock("WIDGET", 0, 0)

    def test_ship_can_use_stock_freed_by_expiry(self):
        self.wh.reserve("o-1", {"WIDGET": 8}, ttl=2.5)
        self.clock.advance(5.0)
        self.wh.ship("WIDGET", 10)
        self.assertStock("WIDGET", 0, 0)
        with self.assertRaises(errors.ReservationExpired):
            self.wh.commit("o-1")
        self.assertStock("WIDGET", 0, 0)

    def test_receive_during_hold_increases_available(self):
        self.wh.reserve("o-1", {"WIDGET": 8}, ttl=30.0)
        self.wh.receive("WIDGET", 5)
        self.assertStock("WIDGET", 15, 7)
        self.wh.commit("o-1")
        self.assertStock("WIDGET", 7, 7)


if __name__ == "__main__":
    unittest.main()
