import unittest
from fractions import Fraction

from calc import CalcSyntaxError, evaluate, parse, to_string


class TestUnary(unittest.TestCase):
    def test_basic_unary_minus(self):
        self.assertEqual(evaluate('-3'), -3)
        self.assertEqual(evaluate('-(1 + 2)'), -3)
        self.assertEqual(evaluate('2 * -3'), -6)
        self.assertEqual(evaluate('1 - -1'), 2)
        self.assertEqual(evaluate('-1 - 1'), -2)

    def test_stacked_signs(self):
        self.assertEqual(evaluate('--1'), 1)
        self.assertEqual(evaluate('-+-1'), 1)
        self.assertEqual(evaluate('+3 - +2'), 1)

    def test_unary_with_multiplication(self):
        self.assertEqual(evaluate('-6 / 2 * 3'), -9)
        self.assertEqual(evaluate('-2 * -2'), 4)


class TestPower(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(evaluate('2 ^ 10'), 1024)
        self.assertEqual(evaluate('2 * 3 ^ 2'), 18)
        self.assertEqual(evaluate('(2 * 3) ^ 2'), 36)
        self.assertEqual(evaluate('1 + 2 ^ 2'), 5)

    def test_right_associative(self):
        self.assertEqual(evaluate('2 ^ 3 ^ 2'), 512)
        self.assertEqual(evaluate('(2 ^ 3) ^ 2'), 64)

    def test_power_binds_tighter_than_unary_minus(self):
        self.assertEqual(evaluate('-2 ^ 2'), -4)
        self.assertEqual(evaluate('(-2) ^ 2'), 4)
        self.assertEqual(evaluate('-2 ^ 3'), -8)

    def test_negative_exponents_are_exact(self):
        result = evaluate('2 ^ -1')
        self.assertIsInstance(result, Fraction)
        self.assertEqual(result, Fraction(1, 2))
        self.assertEqual(evaluate('-2 ^ -2'), Fraction(-1, 4))
        self.assertEqual(evaluate('(1 / 2) ^ -3'), 8)
        self.assertEqual(evaluate('2 ^ -1 ^ 2'), Fraction(1, 2))

    def test_exponent_from_expression(self):
        self.assertEqual(evaluate('4 ^ (4 / 2)'), 16)
        self.assertEqual(evaluate('1.5 ^ 2'), Fraction(9, 4))
        self.assertEqual(evaluate('7 ^ 0'), 1)

    def test_non_integer_exponent_rejected(self):
        for text in ['4 ^ (1 / 2)', '2 ^ 0.5', '8 ^ -(1 / 3)']:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    evaluate(text)

    def test_zero_to_negative_power(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate('0 ^ -1')

    def test_syntax_errors(self):
        for text in ['2 ^', '^ 2', '2 ^ ^ 3', '-', '2 * ', '(-)', '2 ^ * 3', '2 -']:
            with self.subTest(text=text):
                with self.assertRaises(CalcSyntaxError):
                    evaluate(text)


class TestPrinting(unittest.TestCase):
    def compact(self, source):
        return to_string(parse(source)).replace(' ', '')

    def test_minimal_parentheses_for_new_operators(self):
        self.assertEqual(self.compact('-2 ^ 2'), '-2^2')
        self.assertEqual(self.compact('(-2) ^ 2'), '(-2)^2')
        self.assertEqual(self.compact('2 ^ 3 ^ 2'), '2^3^2')
        self.assertEqual(self.compact('(2 ^ 3) ^ 2'), '(2^3)^2')
        self.assertEqual(self.compact('-(1 + 2)'), '-(1+2)')
        self.assertEqual(self.compact('(1 + 2) ^ 2'), '(1+2)^2')
        self.assertEqual(self.compact('2 * 3 ^ 2'), '2*3^2')

    def test_round_trip_preserves_value(self):
        sources = [
            '-2 ^ 2', '(-2) ^ 2', '2 ^ 3 ^ 2', '(2 ^ 3) ^ 2', '2 ^ -1', '-(1 + 2) * 3',
            '1 - -2', '2 * -3', '-2 ^ -2', '(1 / 2) ^ -3', '-(2 ^ 2) ^ 3', '(-1) ^ 3 ^ 2',
            '1.5 ^ 2', '-(-(3))', '2 ^ (1 + 1)', '(2 - 5) ^ 2 * -1', '+3 - +2', '--2 ^ 2',
            '(-(2 ^ 3)) ^ 2', '2 ^ (-2) ^ 2',
        ]
        for source in sources:
            with self.subTest(source=source):
                text = to_string(parse(source))
                self.assertEqual(evaluate(text), evaluate(source), text)


if __name__ == '__main__':
    unittest.main()
