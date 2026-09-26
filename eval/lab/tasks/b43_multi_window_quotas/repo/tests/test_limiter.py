import unittest

from throttle.clock import ManualClock
from throttle.limiter import RateLimiter
from throttle.quotas import QuotaPolicy


def make_limiter(windows):
    policy = QuotaPolicy()
    policy.define_tier('free', windows)
    clock = ManualClock()
    return RateLimiter(policy, clock), clock


def summary(decision):
    return (decision.allowed, decision.remaining, decision.retry_after)


class RateLimiterTests(unittest.TestCase):
    def test_allows_up_to_the_limit(self):
        limiter, _ = make_limiter({'w': (3, 10)})
        self.assertEqual(
            [summary(limiter.check('u')) for _ in range(3)],
            [(True, 2, 0.0), (True, 1, 0.0), (True, 0, 0.0)],
        )
        self.assertEqual(summary(limiter.check('u')), (False, 0, 10.0))

    def test_retry_after_counts_from_the_oldest_event(self):
        limiter, clock = make_limiter({'w': (3, 10)})
        for _ in range(3):
            limiter.check('u')
        clock.advance(4)
        self.assertEqual(summary(limiter.check('u')), (False, 0, 6.0))

    def test_window_slides(self):
        limiter, clock = make_limiter({'w': (3, 10)})
        for _ in range(3):
            limiter.check('u')
        clock.advance(11)
        self.assertEqual(summary(limiter.check('u')), (True, 2, 0.0))

    def test_denied_requests_are_not_recorded(self):
        limiter, clock = make_limiter({'w': (2, 10)})
        limiter.check('u')
        limiter.check('u')
        clock.advance(5)
        self.assertFalse(limiter.check('u').allowed)
        clock.advance(6)
        self.assertEqual(summary(limiter.check('u')), (True, 1, 0.0))
        self.assertEqual(summary(limiter.check('u')), (True, 0, 0.0))

    def test_cost_is_weighted(self):
        limiter, _ = make_limiter({'w': (5, 10)})
        self.assertEqual(summary(limiter.check('u', cost=3)), (True, 2, 0.0))
        self.assertEqual(summary(limiter.check('u', cost=3)), (False, 2, 10.0))
        self.assertEqual(summary(limiter.check('u', cost=2)), (True, 0, 0.0))

    def test_peek_does_not_record(self):
        limiter, _ = make_limiter({'w': (2, 10)})
        self.assertEqual(summary(limiter.peek('u')), (True, 1, 0.0))
        self.assertEqual(summary(limiter.peek('u')), (True, 1, 0.0))
        limiter.check('u')
        limiter.check('u')
        self.assertEqual(summary(limiter.peek('u')), (False, 0, 10.0))

    def test_users_are_independent(self):
        limiter, _ = make_limiter({'w': (1, 10)})
        self.assertTrue(limiter.check('u').allowed)
        self.assertFalse(limiter.check('u').allowed)
        self.assertTrue(limiter.check('v').allowed)

    def test_invalid_cost(self):
        limiter, _ = make_limiter({'w': (1, 10)})
        for cost in (0, -1, 1.5):
            with self.subTest(cost=cost):
                with self.assertRaises(ValueError):
                    limiter.check('u', cost=cost)
                with self.assertRaises(ValueError):
                    limiter.peek('u', cost=cost)

    def test_reset_forgets_user(self):
        limiter, _ = make_limiter({'w': (1, 10)})
        limiter.check('u')
        limiter.reset('u')
        self.assertTrue(limiter.check('u').allowed)
