import unittest
from decimal import Decimal

from statements.amounts import parse_amount


class SeparatorTest(unittest.TestCase):
    CASES = {
        "1234.56": "1234.56",
        "1,234.56": "1234.56",
        "1.234,56": "1234.56",
        "-1.234,56": "-1234.56",
        "1,234,567.89": "1234567.89",
        "1.234.567,89": "1234567.89",
        "12,5": "12.5",
        "12,50": "12.50",
        "0,99": "0.99",
        "1,234": "1234",
        "1.234": "1234",
        "1.234.567": "1234567",
        "1,000,000": "1000000",
    }

    def test_cases(self):
        for text, expected in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(parse_amount(text), Decimal(expected))


class SignAndSymbolTest(unittest.TestCase):
    CASES = {
        "(1,234.56)": "-1234.56",
        "(12,50)": "-12.50",
        "€12,50": "12.50",
        "12,50 €": "12.50",
        "12,50€": "12.50",
        "EUR 1.234,56": "1234.56",
        "1.234,56 EUR": "1234.56",
        "£3": "3",
        "$ 7.25": "7.25",
        "-€5,00": "-5.00",
        "€-5,00": "-5.00",
        "(€5.00)": "-5.00",
        "  USD 10.00  ": "10.00",
        "$1,234.56": "1234.56",
    }

    def test_cases(self):
        for text, expected in self.CASES.items():
            with self.subTest(text=text):
                self.assertEqual(parse_amount(text), Decimal(expected))


class InvalidTest(unittest.TestCase):
    def test_rejects(self):
        for bad in ("", "   ", "abc", "EUR", "1.2.3", "12,34.56", "(5.00", "1..0", "5 apples"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_amount(bad)


if __name__ == "__main__":
    unittest.main()
