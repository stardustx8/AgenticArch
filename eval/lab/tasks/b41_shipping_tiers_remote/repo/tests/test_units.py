import unittest
from decimal import Decimal

from shipping.units import UnknownUnit, to_cm, to_grams


class UnitsTest(unittest.TestCase):
    def test_grams_are_rounded_up(self):
        self.assertEqual(to_grams(1, 'lb'), 454)
        self.assertEqual(to_grams(3, 'oz'), 86)
        self.assertEqual(to_grams('2.5', 'kg'), 2500)
        self.assertEqual(to_grams('0.0001', 'kg'), 1)

    def test_rejects_bad_input(self):
        with self.assertRaises(UnknownUnit):
            to_grams(1, 'stone')
        with self.assertRaises(ValueError):
            to_grams(0, 'kg')

    def test_inches_to_cm(self):
        self.assertEqual(to_cm(10, 'in'), Decimal('25.40'))


if __name__ == '__main__':
    unittest.main()
