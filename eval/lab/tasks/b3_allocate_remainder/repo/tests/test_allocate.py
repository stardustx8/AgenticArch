import unittest

from allocate import allocate
from invoice import split_invoice
from money import format_cents, parse_amount


class TestMoney(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_amount('12.34'), 1234)
        self.assertEqual(parse_amount(' 12.345 '), 1235)
        self.assertEqual(parse_amount('-3.5'), -350)
        self.assertEqual(parse_amount('7'), 700)

    def test_parse_rejects_garbage(self):
        for text in ['', 'abc', 'NaN', 'inf']:
            with self.assertRaises(ValueError):
                parse_amount(text)

    def test_format(self):
        self.assertEqual(format_cents(123456), '1234.56')
        self.assertEqual(format_cents(-5), '-0.05')
        self.assertEqual(format_cents(0), '0.00')


class TestAllocate(unittest.TestCase):
    def test_even_split(self):
        self.assertEqual(allocate(100, [1, 1]), [50, 50])
        self.assertEqual(allocate(100, [1, 3]), [25, 75])

    def test_total_preserved(self):
        for total in (1, 10, 99, 1001):
            for weights in ([1, 1, 1], [2, 5, 7], [1, 0, 1]):
                self.assertEqual(sum(allocate(total, weights)), total)

    def test_zero_total(self):
        self.assertEqual(allocate(0, [1, 2]), [0, 0])

    def test_bad_weights(self):
        for weights in ([], [0, 0]):
            with self.assertRaises(ValueError):
                allocate(100, weights)


class TestInvoice(unittest.TestCase):
    def test_even_invoice(self):
        self.assertEqual(split_invoice('10.00', {'ann': 1, 'bob': 1}), {'ann': '5.00', 'bob': '5.00'})


if __name__ == '__main__':
    unittest.main()
