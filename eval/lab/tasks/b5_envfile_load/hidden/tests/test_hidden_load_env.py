import unittest

from envfile import dump_env, load_env


class HiddenLoadEnvTests(unittest.TestCase):
    def test_basic(self):
        text = 'A=1\n\n# comment\n  B = two  \n'
        self.assertEqual(load_env(text), {'A': '1', 'B': 'two'})

    def test_values_containing_equals(self):
        self.assertEqual(load_env('TOKEN=YWJjZA==\n'), {'TOKEN': 'YWJjZA=='})
        self.assertEqual(load_env('DSN=postgres://u:p@db/app?sslmode=require\n'),
                         {'DSN': 'postgres://u:p@db/app?sslmode=require'})

    def test_hash_inside_value_is_kept(self):
        self.assertEqual(load_env('PASSWORD=p#ss#word\n'), {'PASSWORD': 'p#ss#word'})

    def test_only_one_pair_of_quotes_removed(self):
        self.assertEqual(load_env('MSG="say "hi""\n'), {'MSG': 'say "hi"'})
        self.assertEqual(load_env('EMPTY=""\n'), {'EMPTY': ''})
        self.assertEqual(load_env('Q="\n'), {'Q': '"'})

    def test_round_trip(self):
        data = {
            'TOKEN': 'YWJjZA==',
            'DSN': 'postgres://u:p@db/app?sslmode=require',
            'PASSWORD': 'p#ss=w"rd',
            'EMPTY': '',
            'GREETING': ' hello there ',
            'MSG': 'say "hi"',
            'PLAIN': 'value',
        }
        self.assertEqual(load_env(dump_env(data)), data)

    def test_empty_text(self):
        self.assertEqual(load_env(''), {})
