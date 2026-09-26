import unittest

from shop.pricing import COUPONS, add_tax, apply_discount, checkout_total


class HiddenCheckoutTests(unittest.TestCase):
    def test_no_coupon(self):
        self.assertEqual(checkout_total([(1250, 2), (999, 1)]), 3787)

    def test_with_coupon(self):
        self.assertEqual(checkout_total([(995, 1)], 'SAVE10'), 968)
        self.assertEqual(checkout_total([(1250, 2), (999, 1)], 'HALF'), 1893)

    def test_coupon_code_case_insensitive(self):
        self.assertEqual(checkout_total([(995, 1)], 'save10'), 968)
        self.assertEqual(checkout_total([(995, 1)], 'Half'), checkout_total([(995, 1)], 'HALF'))

    def test_unknown_coupon(self):
        with self.assertRaises(ValueError):
            checkout_total([(995, 1)], 'BOGUS')

    def test_empty_cart(self):
        self.assertEqual(checkout_total([]), 0)

    def test_coupon_table(self):
        self.assertEqual(COUPONS['SAVE10'], 10)
        self.assertEqual(COUPONS['HALF'], 50)

    def test_matches_existing_helpers(self):
        cases = [([(333, 3)], 'SAVE10'), ([(1999, 1), (1, 7)], 'HALF'), ([(4321, 2)], None)]
        for items, code in cases:
            subtotal = sum(price * qty for price, qty in items)
            if code:
                subtotal = apply_discount(subtotal, COUPONS[code])
            self.assertEqual(checkout_total(items, code), add_tax(subtotal))
