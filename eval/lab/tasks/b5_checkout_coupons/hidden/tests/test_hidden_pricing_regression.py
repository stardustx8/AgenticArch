import unittest

from shop.pricing import add_tax, apply_discount, checkout_total, shipping_fee


class HiddenPricingRegressionTests(unittest.TestCase):
    def test_discount_rounds_down(self):
        self.assertEqual(apply_discount(995, 15), 845)
        self.assertEqual(apply_discount(1999, 10), 1799)
        self.assertEqual(apply_discount(1, 50), 0)

    def test_tax_rounds_down(self):
        self.assertEqual(add_tax(1100), 1190)
        self.assertEqual(add_tax(3499), 3787)
        self.assertEqual(add_tax(1), 1)

    def test_shipping_unchanged(self):
        self.assertEqual(shipping_fee(None), 0)
        self.assertEqual(shipping_fee(500), 499)
        self.assertEqual(shipping_fee(501), 899)
        self.assertEqual(shipping_fee(2000), 899)
        self.assertEqual(shipping_fee(2001), 1149)
        self.assertEqual(shipping_fee(3000), 1149)
        self.assertEqual(shipping_fee(3500), 1399)
        self.assertEqual(shipping_fee(4001), 1649)

    def test_checkout_uses_floor_rules(self):
        self.assertEqual(checkout_total([(1100, 1)]), 1190)
        self.assertEqual(checkout_total([(995, 1)], 'HALF'), add_tax(497))
