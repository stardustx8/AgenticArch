import unittest

from shop import add_tax, apply_discount, shipping_fee


class PricingTests(unittest.TestCase):
    def test_discount(self):
        self.assertEqual(apply_discount(1000, 10), 900)
        self.assertEqual(apply_discount(1000, 0), 1000)
        self.assertEqual(apply_discount(1000, 100), 0)

    def test_discount_range(self):
        with self.assertRaises(ValueError):
            apply_discount(1000, 101)

    def test_tax(self):
        self.assertEqual(add_tax(10000), 10825)

    def test_shipping(self):
        self.assertEqual(shipping_fee(100), 499)
        self.assertEqual(shipping_fee(1500), 899)


if __name__ == '__main__':
    unittest.main()
