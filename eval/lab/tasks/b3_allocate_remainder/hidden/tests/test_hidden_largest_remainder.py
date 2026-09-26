import unittest

from allocate import allocate
from invoice import split_invoice


class TestLargestRemainder(unittest.TestCase):
    def test_extra_cent_goes_to_first_on_ties(self):
        self.assertEqual(allocate(100, [1, 1, 1]), [34, 33, 33])
        self.assertEqual(allocate(2, [1, 1, 1]), [1, 1, 0])
        self.assertEqual(allocate(5, [1, 1, 1, 1]), [2, 1, 1, 1])
        self.assertEqual(allocate(7, [1, 1]), [4, 3])

    def test_largest_remainder_wins(self):
        self.assertEqual(allocate(10, [1, 5]), [2, 8])
        self.assertEqual(allocate(100, [2, 1, 1, 3]), [29, 14, 14, 43])
        self.assertEqual(allocate(100, [3, 3, 1]), [43, 43, 14])

    def test_no_share_moves_a_full_cent_from_exact(self):
        for total in range(0, 250, 3):
            for weights in ([1, 2, 3], [5, 1], [1, 1, 1, 1, 1, 1, 1], [10, 0, 3, 7]):
                shares = allocate(total, weights)
                self.assertEqual(sum(shares), total)
                weight_sum = sum(weights)
                for share, w in zip(shares, weights):
                    self.assertLess(abs(share - total * w / weight_sum), 1, (total, weights, shares))

    def test_zero_weights_get_nothing(self):
        self.assertEqual(allocate(1, [1, 0]), [1, 0])
        self.assertEqual(allocate(5, [0, 1, 1, 0]), [0, 3, 2, 0])
        for total in range(0, 50):
            shares = allocate(total, [0, 2, 0, 1, 0])
            self.assertEqual((shares[0], shares[2], shares[4]), (0, 0, 0))
            self.assertEqual(sum(shares), total)

    def test_negative_weights_rejected(self):
        with self.assertRaises(ValueError):
            allocate(100, [2, -1])
        with self.assertRaises(ValueError):
            allocate(100, [1, -1, 1])

    def test_refunds_mirror_charges(self):
        self.assertEqual(allocate(-100, [1, 1, 1]), [-34, -33, -33])
        self.assertEqual(allocate(-10, [1, 5]), [-2, -8])
        for total in range(1, 120, 11):
            for weights in ([1, 2, 3], [7, 0, 2], [1, 1]):
                self.assertEqual(allocate(-total, weights), [-s for s in allocate(total, weights)])

    def test_accepts_any_iterable(self):
        self.assertEqual(allocate(100, (w for w in [1, 1, 1])), [34, 33, 33])


class TestUnits(unittest.TestCase):
    def test_multiples_of_unit(self):
        self.assertEqual(allocate(100, [1, 1, 1], unit=5), [35, 35, 30])
        self.assertEqual(allocate(-100, [1, 1, 1], unit=5), [-35, -35, -30])
        self.assertEqual(allocate(100, [1, 1], unit=100), [100, 0])

    def test_unit_invariants(self):
        for total in range(0, 500, 25):
            for weights in ([1, 2, 3], [3, 3, 1], [1, 0, 1]):
                shares = allocate(total, weights, unit=5)
                self.assertEqual(sum(shares), total)
                for share in shares:
                    self.assertEqual(share % 5, 0)

    def test_total_must_be_multiple_of_unit(self):
        with self.assertRaises(ValueError):
            allocate(101, [1, 1], unit=5)
        with self.assertRaises(ValueError):
            allocate(-7, [1, 1], unit=5)

    def test_default_unit_is_one_cent(self):
        self.assertEqual(allocate(7, [1, 1]), [4, 3])


class TestInvoiceSplits(unittest.TestCase):
    def test_three_way_split(self):
        self.assertEqual(
            split_invoice('0.10', {'ann': 1, 'bob': 1, 'cy': 1}),
            {'ann': '0.04', 'bob': '0.03', 'cy': '0.03'},
        )

    def test_refund_split(self):
        self.assertEqual(
            split_invoice('-1.00', {'ann': 1, 'bob': 1, 'cy': 1}),
            {'ann': '-0.34', 'bob': '-0.33', 'cy': '-0.33'},
        )

    def test_cash_split(self):
        self.assertEqual(
            split_invoice('1.00', {'ann': 1, 'bob': 1, 'cy': 1}, unit=5),
            {'ann': '0.35', 'bob': '0.35', 'cy': '0.30'},
        )

    def test_zero_weight_person_pays_nothing(self):
        self.assertEqual(split_invoice('0.01', {'ann': 1, 'guest': 0}), {'ann': '0.01', 'guest': '0.00'})


if __name__ == '__main__':
    unittest.main()
