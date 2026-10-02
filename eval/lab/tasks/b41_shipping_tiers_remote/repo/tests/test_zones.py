import unittest

from shipping.zones import InvalidPostalCode, normalize_zip, zone_for


class ZonesTest(unittest.TestCase):
    def test_normalizes_zip_plus_four(self):
        self.assertEqual(normalize_zip(' 30301-1234 '), '30301')

    def test_rejects_invalid_codes(self):
        for bad in ('3030', 'ABCDE', '303011'):
            with self.subTest(bad=bad), self.assertRaises(InvalidPostalCode):
                normalize_zip(bad)

    def test_zone_by_distance(self):
        self.assertEqual(zone_for('10001', '10002'), 1)
        self.assertEqual(zone_for('10001', '11201'), 2)
        self.assertEqual(zone_for('10001', '20001'), 2)
        self.assertEqual(zone_for('10001', '30301'), 3)
        self.assertEqual(zone_for('10001', '60601'), 4)
        self.assertEqual(zone_for('10001', '90210'), 5)


if __name__ == '__main__':
    unittest.main()
