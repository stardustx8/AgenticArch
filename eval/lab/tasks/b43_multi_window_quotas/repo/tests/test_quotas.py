import unittest

from throttle.errors import QuotaError, UnknownTierError
from throttle.quotas import QuotaPolicy, Window


class QuotaPolicyTests(unittest.TestCase):
    def test_default_tier_applies(self):
        policy = QuotaPolicy()
        policy.define_tier('free', {'minute': (10, 60)})
        self.assertEqual(policy.windows_for('anyone'), (Window('minute', 10, 60.0),))

    def test_assignment(self):
        policy = QuotaPolicy()
        policy.define_tier('free', {'minute': (10, 60)})
        policy.define_tier('pro', {'minute': (100, 60)})
        policy.assign('alice', 'pro')
        self.assertEqual(policy.tier_of('alice'), 'pro')
        self.assertEqual(policy.windows_for('alice')[0].limit, 100)
        self.assertEqual(policy.windows_for('bob')[0].limit, 10)

    def test_override_replaces_same_named_window(self):
        policy = QuotaPolicy()
        policy.define_tier('free', {'minute': (10, 60)})
        policy.override('alice', {'minute': (25, 60)})
        self.assertEqual(policy.windows_for('alice'), (Window('minute', 25, 60.0),))
        self.assertEqual(policy.windows_for('bob'), (Window('minute', 10, 60.0),))
        policy.clear_override('alice')
        self.assertEqual(policy.windows_for('alice'), (Window('minute', 10, 60.0),))

    def test_unknown_tier(self):
        policy = QuotaPolicy()
        with self.assertRaises(UnknownTierError):
            policy.windows_for('anyone')
        with self.assertRaises(UnknownTierError):
            policy.assign('alice', 'gold')

    def test_invalid_windows(self):
        policy = QuotaPolicy()
        bad = [{}, {'minute': (0, 60)}, {'minute': (5, 0)}, {'': (5, 60)}, {'minute': (2.5, 60)}]
        for windows in bad:
            with self.subTest(windows=windows):
                with self.assertRaises(QuotaError):
                    policy.define_tier('free', windows)
