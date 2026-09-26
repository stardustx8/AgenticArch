import unittest

from shipping.advisor import weight_headroom
from shipping.package import Package
from shipping.quote import quote_package
from shipping.tiers import Overweight, table_for


class InclusiveTierLimitTest(unittest.TestCase):
    def test_parcel_on_a_limit_stays_in_that_tier(self):
        quote = quote_package(Package(2), '10001', '10002')
        self.assertEqual((quote.billable_grams, quote.base, quote.fuel, quote.total), (2000, 810, 69, 879))
        quote = quote_package(Package(500, 'g'), '10001', '30301')
        self.assertEqual((quote.base, quote.total), (700, 760))
        quote = quote_package(Package(1, 'kg'), '10001', '20001', service='express')
        self.assertEqual(quote.base, 1400)

    def test_one_gram_over_moves_up(self):
        quote = quote_package(Package(2001, 'g'), '10001', '10002')
        self.assertEqual(quote.base, 1150)

    def test_table_boundaries(self):
        table = table_for('standard')
        self.assertEqual(table.base_price(500, 1), 520)
        self.assertEqual(table.base_price(501, 1), 640)
        self.assertEqual(table.base_price(10000, 4), 2830)
        self.assertEqual(table.base_price(20000, 5), 5400)

    def test_dimensional_weight_on_a_limit(self):
        # 20 x 10 x 25 cm = 5000 cm3 -> exactly 1000 g
        quote = quote_package(Package(200, 'g', dims=(20, 10, 25)), '10001', '10002')
        self.assertEqual((quote.billable_grams, quote.base), (1000, 640))


class WeightHeadroomTest(unittest.TestCase):
    def test_headroom_counts_up_to_and_including_the_limit(self):
        self.assertEqual(weight_headroom(1), 499)
        self.assertEqual(weight_headroom(1999), 1)
        self.assertEqual(weight_headroom(2000), 0)
        self.assertEqual(weight_headroom(2001), 2999)
        self.assertEqual(weight_headroom(500, 'express'), 0)
        self.assertEqual(weight_headroom(20000), 0)


class HeavyweightTest(unittest.TestCase):
    def test_exactly_top_tier_has_no_extra(self):
        quote = quote_package(Package(20), '10001', '90210')
        self.assertEqual((quote.zone, quote.base, quote.fuel, quote.total), (5, 5400, 459, 5859))

    def test_every_started_kg_above_top_tier_is_charged(self):
        cases = [('20.001', 5610), ('21', 5610), ('21.001', 5820), ('25.5', 5400 + 6 * 210)]
        for weight, base in cases:
            with self.subTest(weight=weight):
                self.assertEqual(quote_package(Package(weight), '10001', '90210').base, base)
        quote = quote_package(Package('20.001'), '10001', '90210')
        self.assertEqual((quote.fuel, quote.total), (477, 6087))

    def test_heavy_express_quote(self):
        quote = quote_package(Package('20.5'), '10001', '10002', service='express')
        self.assertEqual((quote.base, quote.fuel, quote.total), (5120, 589, 5709))

    def test_actual_weight_limit_is_70kg(self):
        quote = quote_package(Package(70), '10001', '10002')
        self.assertEqual((quote.base, quote.fuel, quote.total), (7350, 625, 7975))
        with self.assertRaises(Overweight):
            quote_package(Package('70.001'), '10001', '10002')

    def test_light_bulky_parcel_is_priced_on_dimensional_weight(self):
        quote = quote_package(Package(1, dims=(100, 100, 50)), '10001', '10002')
        self.assertEqual(
            (quote.billable_grams, quote.base, quote.fuel, quote.total),
            (100000, 10200, 867, 11067),
        )


if __name__ == '__main__':
    unittest.main()
