import unittest

from envfile import dump_env


class DumpEnvTests(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(dump_env({'A': '1', 'B': 'x'}), 'A=1\nB=x\n')

    def test_quotes_when_needed(self):
        self.assertEqual(dump_env({'G': 'hi there', 'E': ''}), 'G="hi there"\nE=""\n')

    def test_non_string_values(self):
        self.assertEqual(dump_env({'N': 3}), 'N=3\n')

    def test_empty(self):
        self.assertEqual(dump_env({}), '')


if __name__ == '__main__':
    unittest.main()
