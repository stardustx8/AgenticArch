import unittest

from sorting import latest, sort_versions
from version import Version

SPEC_ORDER = [
    '1.0.0-alpha',
    '1.0.0-alpha.1',
    '1.0.0-alpha.beta',
    '1.0.0-beta',
    '1.0.0-beta.2',
    '1.0.0-beta.11',
    '1.0.0-rc.1',
    '1.0.0',
]


def v(text):
    return Version.parse(text)


class TestPrecedence(unittest.TestCase):
    def test_spec_example_order(self):
        shuffled = [SPEC_ORDER[i] for i in (7, 3, 0, 6, 5, 1, 4, 2)]
        self.assertEqual(sort_versions(shuffled), SPEC_ORDER)

    def test_pairwise_spec_order(self):
        for lo_text, hi_text in zip(SPEC_ORDER, SPEC_ORDER[1:]):
            with self.subTest(lo=lo_text, hi=hi_text):
                lo, hi = v(lo_text), v(hi_text)
                self.assertLess(lo, hi)
                self.assertGreater(hi, lo)
                self.assertNotEqual(lo, hi)

    def test_numeric_identifiers_compare_numerically(self):
        self.assertEqual(
            sort_versions(['2.0.0-rc.10', '2.0.0-rc.2', '2.0.0-rc.1']),
            ['2.0.0-rc.1', '2.0.0-rc.2', '2.0.0-rc.10'],
        )
        self.assertLess(v('1.0.0-9'), v('1.0.0-10'))

    def test_numeric_ranks_below_alphanumeric(self):
        self.assertLess(v('1.0.0-1'), v('1.0.0-alpha'))
        self.assertLess(v('1.0.0-alpha.99'), v('1.0.0-alpha.a'))
        self.assertLess(v('1.0.0-alpha.999'), v('1.0.0-alpha.1a'))

    def test_release_outranks_its_prereleases(self):
        self.assertLess(v('2.0.0-rc.1'), v('2.0.0'))
        self.assertLess(v('2.0.0'), v('2.0.1-alpha'))
        self.assertEqual(sort_versions(['2.0.0', '2.0.0-rc.1']), ['2.0.0-rc.1', '2.0.0'])

    def test_longer_prerelease_wins_when_prefix_equal(self):
        self.assertLess(v('1.0.0-alpha'), v('1.0.0-alpha.0'))
        self.assertLess(v('1.0.0-alpha.1'), v('1.0.0-alpha.1.1'))

    def test_build_metadata_ignored(self):
        self.assertEqual(v('1.0.0+build.1'), v('1.0.0+build.2'))
        self.assertFalse(v('1.0.0+b') < v('1.0.0+a'))
        self.assertFalse(v('1.0.0+a') < v('1.0.0+b'))
        self.assertEqual(v('1.0.0-rc.1+x'), v('1.0.0-rc.1'))
        self.assertLess(v('1.0.0-rc.1+zzz'), v('1.0.0+aaa'))
        self.assertEqual(len({v('1.0.0+a'), v('1.0.0+b')}), 1)

    def test_equal_precedence_keeps_input_order(self):
        self.assertEqual(sort_versions(['1.0.0+b', '1.0.0+a']), ['1.0.0+b', '1.0.0+a'])

    def test_latest_with_prereleases(self):
        self.assertEqual(latest(['2.0.0-rc.1', '2.0.0', '1.9.0'], include_prerelease=True), '2.0.0')
        self.assertEqual(latest(['2.0.0-rc.2', '2.0.0-rc.10', '1.9.0'], include_prerelease=True), '2.0.0-rc.10')
        self.assertEqual(latest(['2.0.0-rc.2', '2.0.0-rc.10', '1.9.0']), '1.9.0')


if __name__ == '__main__':
    unittest.main()
