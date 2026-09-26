import tempfile
import unittest
from decimal import Decimal

from shop import Catalog, OrderRepository, PercentOff, Product, checkout
from shop.discounts import AmountOff


def make_catalog():
    return Catalog([
        Product('X', 'shirt', Decimal('60.00'), 'standard'),
        Product('Y', 'bread', Decimal('40.00'), 'food'),
        Product('Z', 'voucher', Decimal('40.00'), 'exempt'),
        Product('U', 'mug', Decimal('5.00'), 'exempt'),
        Product('V', 'lamp', Decimal('25.00'), 'exempt'),
        Product('W1', 'cup', Decimal('10.00'), 'exempt'),
        Product('W2', 'bowl', Decimal('10.00'), 'exempt'),
        Product('W3', 'plate', Decimal('10.00'), 'exempt'),
        Product('B', 'book', Decimal('10.00'), 'standard', price_breaks=((5, Decimal('9.00')),)),
    ])


def discounts(order):
    return [line.discount for line in order.lines]


class AmountOffTests(unittest.TestCase):
    def setUp(self):
        self.catalog = make_catalog()

    def test_split_proportionally_and_taxed_per_line(self):
        order = checkout('a1', 'DE', [('X', 1), ('Y', 1)], self.catalog, coupon=AmountOff('10'))
        self.assertEqual(discounts(order), [Decimal('6.00'), Decimal('4.00')])
        self.assertEqual([l.tax for l in order.lines], [Decimal('10.26'), Decimal('2.52')])
        self.assertEqual(order.total, Decimal('102.78'))

    def test_exempt_line_absorbs_its_share(self):
        order = checkout('a2', 'DE', [('X', 1), ('Z', 1)], self.catalog, coupon=AmountOff('10'))
        self.assertEqual(discounts(order), [Decimal('6.00'), Decimal('4.00')])
        self.assertEqual(order.tax_total, Decimal('10.26'))
        self.assertEqual(order.total, Decimal('100.26'))

    def test_leftover_cent_goes_to_largest_line(self):
        order = checkout('a3', 'DE', [('U', 2), ('V', 1), ('W1', 1)], self.catalog,
                         coupon=AmountOff('10'))
        self.assertEqual(discounts(order), [Decimal('2.22'), Decimal('5.56'), Decimal('2.22')])
        self.assertEqual(order.discount_total, Decimal('10.00'))

    def test_leftover_tie_goes_to_first_line(self):
        order = checkout('a4', 'DE', [('W1', 1), ('W2', 1), ('W3', 1)], self.catalog,
                         coupon=AmountOff('10'))
        self.assertEqual(discounts(order), [Decimal('3.34'), Decimal('3.33'), Decimal('3.33')])

    def test_all_leftover_cents_go_to_one_line(self):
        order = checkout('a5', 'DE', [('W1', 1), ('W2', 1), ('W3', 1)], self.catalog,
                         coupon=AmountOff('0.20'))
        self.assertEqual(discounts(order), [Decimal('0.08'), Decimal('0.06'), Decimal('0.06')])

    def test_coupon_capped_at_subtotal(self):
        order = checkout('a6', 'DE', [('W1', 1), ('U', 2)], self.catalog, coupon=AmountOff('50'))
        self.assertEqual(order.discount_total, Decimal('20.00'))
        self.assertEqual(order.total, Decimal('0'))
        for line in order.lines:
            self.assertEqual(line.net, Decimal('0'))

    def test_capped_coupon_leaves_no_tax(self):
        order = checkout('a7', 'DE', [('X', 1)], self.catalog, coupon=AmountOff('75'))
        self.assertEqual(order.discount_total, Decimal('60.00'))
        self.assertEqual(order.tax_total, Decimal('0'))
        self.assertEqual(order.total, Decimal('0'))

    def test_coupon_on_break_priced_line(self):
        order = checkout('a8', 'DE', [('B', 5)], self.catalog, coupon=AmountOff('4.50'))
        self.assertEqual(order.discount_total, Decimal('4.50'))
        self.assertEqual(order.tax_total, Decimal('7.70'))
        self.assertEqual(order.total, Decimal('48.20'))

    def test_percent_coupon_still_works(self):
        order = checkout('a9', 'DE', [('B', 2)], self.catalog, coupon=PercentOff(10))
        self.assertEqual(order.total, Decimal('21.42'))


class AmountOffPersistenceTests(unittest.TestCase):
    def test_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = OrderRepository(tmp)
            order = checkout('a10', 'DE', [('X', 1), ('Y', 1)], make_catalog(),
                             coupon=AmountOff('10'), repository=repo)
            loaded = repo.load('a10')
            self.assertIsInstance(loaded.coupon, AmountOff)
            self.assertEqual(loaded.total, order.total)
            loaded.coupon.apply(loaded.lines)
            self.assertEqual(discounts(loaded), discounts(order))


if __name__ == '__main__':
    unittest.main()
