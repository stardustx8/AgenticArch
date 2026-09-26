import unittest

from shipping.package import Package
from shipping.shipment import Shipment


class ShipmentTest(unittest.TestCase):
    def test_total_is_sum_of_package_quotes(self):
        shipment = Shipment('10001', '10002').add(Package('1.2')).add(Package(300, 'g'))
        self.assertEqual(len(shipment.quotes()), 2)
        self.assertEqual(shipment.total(), 1443)

    def test_empty_shipment(self):
        with self.assertRaises(ValueError):
            Shipment('10001', '10002').total()


if __name__ == '__main__':
    unittest.main()
