import unittest

from throttle.clock import ManualClock
from throttle.limiter import RateLimiter
from throttle.quotas import QuotaPolicy, Window


def summary(decision):
    return (decision.allowed, decision.remaining, decision.retry_after)


def make_limiter(windows):
    policy = QuotaPolicy()
    policy.define_tier('free', windows)
    clock = ManualClock()
    return RateLimiter(policy, clock), policy, clock


class MultiWindowTests(unittest.TestCase):
    def test_tier_with_several_windows(self):
        policy = QuotaPolicy()
        policy.define_tier('free', {'second': (2, 1), 'minute': (5, 60)})
        self.assertEqual(
            policy.windows_for('u'),
            (Window('second', 2, 1.0), Window('minute', 5, 60.0)),
        )

    def test_every_window_must_have_room(self):
        limiter, _, clock = make_limiter({'second': (2, 1), 'minute': (5, 60)})
        self.assertEqual(summary(limiter.check('u')), (True, 1, 0.0))
        self.assertEqual(summary(limiter.check('u')), (True, 0, 0.0))
        self.assertEqual(summary(limiter.check('u')), (False, 0, 1.0))
        clock.set(1)
        self.assertEqual(summary(limiter.check('u')), (True, 1, 0.0))
        self.assertEqual(summary(limiter.check('u')), (True, 0, 0.0))
        clock.set(2)
        self.assertEqual(summary(limiter.check('u')), (True, 0, 0.0))
        clock.set(3)
        self.assertEqual(summary(limiter.check('u')), (False, 0, 57.0))

    def test_denied_request_is_not_recorded_in_any_window(self):
        limiter, _, clock = make_limiter({'minute': (3, 60), 'second': (1, 1)})
        self.assertTrue(limiter.check('u').allowed)
        self.assertEqual(summary(limiter.check('u')), (False, 0, 1.0))
        self.assertFalse(limiter.check('u').allowed)
        clock.set(1)
        self.assertEqual(summary(limiter.check('u')), (True, 0, 0.0))
        clock.set(2)
        self.assertEqual(summary(limiter.check('u')), (True, 0, 0.0))
        clock.set(3)
        self.assertEqual(summary(limiter.check('u')), (False, 0, 57.0))

    def test_retry_after_is_the_longest_wait(self):
        limiter, _, clock = make_limiter({'burst': (2, 10), 'steady': (3, 100)})
        self.assertTrue(limiter.check('u', cost=2).allowed)
        clock.set(5)
        self.assertEqual(summary(limiter.check('u', cost=2)), (False, 0, 95.0))
        self.assertEqual(summary(limiter.peek('u', cost=2)), (False, 0, 95.0))
        clock.set(100)
        self.assertEqual(summary(limiter.check('u', cost=2)), (True, 0, 0.0))

    def test_cost_larger_than_one_window_can_never_succeed(self):
        limiter, _, _ = make_limiter({'a': (10, 10), 'b': (3, 100)})
        self.assertTrue(limiter.check('u', cost=2).allowed)
        self.assertEqual(summary(limiter.check('u', cost=4)), (False, 1, None))
        self.assertEqual(summary(limiter.peek('u', cost=4)), (False, 1, None))
        self.assertEqual(summary(limiter.check('u', cost=1)), (True, 0, 0.0))

    def test_override_replaces_only_same_named_windows(self):
        limiter, policy, _ = make_limiter({'second': (2, 1), 'minute': (5, 60)})
        policy.override('bob', {'minute': (50, 60), 'hour': (100, 3600)})
        self.assertEqual(
            [(window.name, window.limit) for window in policy.windows_for('bob')],
            [('second', 2), ('minute', 50), ('hour', 100)],
        )
        self.assertEqual(summary(limiter.check('bob')), (True, 1, 0.0))
        self.assertEqual(summary(limiter.check('bob')), (True, 0, 0.0))
        self.assertEqual(summary(limiter.check('bob')), (False, 0, 1.0))
