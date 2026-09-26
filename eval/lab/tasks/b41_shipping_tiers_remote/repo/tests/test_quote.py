import unittest

from shipping.package import Package
from shipping.quote import quote_package
from shipping.tiers import UnknownService


class QuoteTest(unittest.TestCase):
    def test_standard_quote(self):
        quote = quote_package(Package('1.2'), '10001', '10002')
        self.assertEqual(
            (quote.zone, quote.billable_grams, quote.base, quote.fuel, quote.total),
            (1, 1200, 810, 69, 879),
        )

    def test_residential_surcharge_is_fuel_surcharged(self):
        quote = quote_package(Package(300, 'g'), '10001', '30301', residential=True)
        self.assertEqual(quote.base, 700)
        self.assertEqual(quote.residential, 350)
        self.assertEqual(quote.fuel, 89)
        self.assertEqual(quote.total, 1139)

    def test_dimensional_weight_wins_when_heavier(self):
        quote = quote_package(Package('0.5', dims=(30, 30, 30)), '10001', '10002')
        self.assertEqual(quote.billable_grams, 5400)
        self.assertEqual(quote.base, 1690)
        self.assertEqual(quote.total, 1834)

    def test_dimensions_in_inches(self):
        quote = quote_package(Package(1, dims=(12, 12, 12), dim_unit='in'), '10001', '10002')
        self.assertEqual(quote.billable_grams, 5664)

    def test_express(self):
        quote = quote_package(Package(3), '10001', '20001', service='express')
        self.assertEqual((quote.zone, quote.base, quote.fuel, quote.total), (2, 2560, 294, 2854))

    def test_unknown_service(self):
        with self.assertRaises(UnknownService):
            quote_package(Package(1), '10001', '10002', service='overnight')


if __name__ == '__main__':
    unittest.main()
