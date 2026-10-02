import unittest

from sorting import latest, sort_versions
from version import Version


class TestVersion(unittest.TestCase):
    def test_parse(self):
        v = Version.parse('1.2.3-beta.1+build.5')
        self.assertEqual((v.major, v.minor, v.patch), (1, 2, 3))
        self.assertEqual(v.prerelease, ('beta', '1'))
        self.assertEqual(v.build, ('build', '5'))

    def test_str_roundtrip(self):
        for text in ['0.0.1', '1.2.3-rc.1', '1.2.3+exp.sha.5114f85', '1.2.3-a.b+c']:
            self.assertEqual(str(Version.parse(text)), text)

    def test_invalid(self):
        for text in ['1.2', '1.2.x', '', 'a.b.c', '1.2.3.4']:
            with self.assertRaises(ValueError):
                Version.parse(text)

    def test_numeric_core_ordering(self):
        self.assertEqual(
            sort_versions(['1.10.0', '1.2.0', '1.2.10', '1.2.9']),
            ['1.2.0', '1.2.9', '1.2.10', '1.10.0'],
        )

    def test_prerelease_names(self):
        self.assertEqual(sort_versions(['1.0.0-beta', '1.0.0-alpha']), ['1.0.0-alpha', '1.0.0-beta'])

    def test_latest_stable(self):
        self.assertEqual(latest(['1.0.0', '1.1.0-rc.1', '0.9.0']), '1.0.0')

    def test_latest_none(self):
        self.assertIsNone(latest(['1.0.0-rc.1']))


if __name__ == '__main__':
    unittest.main()
