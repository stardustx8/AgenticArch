import unittest

from shipping.package import Package
from shipping.quote import quote_package
from shipping.shipment import Shipment


class RemoteAreaTest(unittest.TestCase):
    def test_remote_destination_is_zone_5_with_fuel_on_the_surcharge(self):
        quote = quote_package(Package(1), '10001', '99501')
        self.assertEqual(quote.zone, 5)
        self.assertEqual(quote.base, 1240)
        self.assertEqual(quote.remote, 1200)
        self.assertEqual(quote.fuel, 207)
        self.assertEqual(quote.total, 2647)

    def test_same_area_remote_delivery_is_still_zone_5(self):
        quote = quote_package(Package('2.5'), '96813', '96822', service='express', residential=True)
        self.assertEqual((quote.zone, quote.base, quote.residential, quote.remote), (5, 4250, 350, 1200))
        self.assertEqual(quote.fuel, 667)
        self.assertEqual(quote.total, 6467)

    def test_padded_zip_plus_four_destination(self):
        quote = quote_package(Package(1), '10001', ' 99701-0001 ')
        self.assertEqual(quote.zone, 5)
        self.assertEqual(quote.remote, 1200)

    def test_remote_origin_does_not_trigger_surcharge(self):
        quote = quote_package(Package(1), '96813', '80202')
        self.assertEqual(
            (quote.zone, quote.remote, quote.base, quote.fuel, quote.total),
            (2, 0, 750, 64, 814),
        )

    def test_regular_destination_has_no_remote_fee(self):
        quote = quote_package(Package('1.2'), '10001', '10002')
        self.assertEqual(quote.remote, 0)
        self.assertEqual(quote.total, 879)

    def test_each_package_in_a_remote_shipment_pays_it(self):
        shipment = Shipment('10001', '99501').add(Package(1)).add(Package(1))
        self.assertEqual(shipment.total(), 2 * 2647)


if __name__ == '__main__':
    unittest.main()
