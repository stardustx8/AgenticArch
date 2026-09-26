import unittest
from fractions import Fraction

from calc import CalcSyntaxError, evaluate, parse, to_string, tokenize


class TestTokenizer(unittest.TestCase):
    def test_kinds(self):
        kinds = [t.kind for t in tokenize('12+(3.5)')]
        self.assertEqual(kinds, ['NUM', 'OP', 'LPAREN', 'NUM', 'RPAREN', 'END'])

    def test_bad_number(self):
        with self.assertRaises(CalcSyntaxError):
            tokenize('1..2')


class TestEvaluate(unittest.TestCase):
    def test_precedence(self):
        self.assertEqual(evaluate('1 + 2 * 3'), 7)
        self.assertEqual(evaluate('(1 + 2) * 3'), 9)
        self.assertEqual(evaluate('10 - 4 - 3'), 3)

    def test_exact_division(self):
        self.assertEqual(evaluate('7 / 2'), Fraction(7, 2))
        self.assertEqual(evaluate('1.5 * 2'), 3)

    def test_division_by_zero(self):
        with self.assertRaises(ZeroDivisionError):
            evaluate('1 / 0')

    def test_syntax_errors(self):
        for text in ['1 +', '(1', '1 2', '$', '* 2', '']:
            with self.assertRaises(CalcSyntaxError):
                evaluate(text)


class TestPrinter(unittest.TestCase):
    def test_minimal_parentheses(self):
        cases = {
            '(1 + 2) * 3': '(1 + 2) * 3',
            '1 - (2 - 3)': '1 - (2 - 3)',
            '(1 - 2) - 3': '1 - 2 - 3',
            '1 + (2 * 3)': '1 + 2 * 3',
            '8 / (4 / 2)': '8 / (4 / 2)',
            '1.5 * 2': '(3/2) * 2',
        }
        for source, expected in cases.items():
            self.assertEqual(to_string(parse(source)), expected)


if __name__ == '__main__':
    unittest.main()
