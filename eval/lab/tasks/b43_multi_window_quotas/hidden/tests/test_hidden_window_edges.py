import unittest

from throttle.clock import ManualClock
from throttle.limiter import RateLimiter
from throttle.quotas import QuotaPolicy
from throttle.window import SlidingLog


def summary(decision):
    return (decision.allowed, decision.remaining, decision.retry_after)


def make_limiter(limit, seconds):
    policy = QuotaPolicy()
    policy.define_tier('free', {'w': (limit, seconds)})
    clock = ManualClock()
    return RateLimiter(policy, clock), clock


class WeightedRetryTests(unittest.TestCase):
    def setUp(self):
        self.limiter, self.clock = make_limiter(5, 10)
        self.limiter.check('u', cost=2)
        self.clock.set(3)
        self.limiter.check('u', cost=2)
        self.clock.set(4)
        self.limiter.check('u', cost=1)
        self.clock.set(5)

    def test_retry_after_waits_for_enough_capacity(self):
        self.assertEqual(summary(self.limiter.check('u', cost=3)), (False, 0, 8.0))

    def test_peek_agrees_with_check(self):
        self.assertEqual(summary(self.limiter.peek('u', cost=3)), (False, 0, 8.0))
        self.assertEqual(summary(self.limiter.peek('u', cost=1)), (False, 0, 5.0))

    def test_request_fits_exactly_when_retry_after_elapses(self):
        self.clock.set(12)
        self.assertEqual(summary(self.limiter.check('u', cost=3)), (False, 2, 1.0))
        self.clock.set(13)
        self.assertEqual(summary(self.limiter.check('u', cost=3)), (True, 1, 0.0))


class OversizedCostTests(unittest.TestCase):
    def test_oversized_cost_never_fits(self):
        limiter, _ = make_limiter(5, 10)
        limiter.check('u', cost=1)
        self.assertEqual(summary(limiter.check('u', cost=6)), (False, 4, None))
        self.assertEqual(summary(limiter.peek('u', cost=6)), (False, 4, None))
        self.assertEqual(summary(limiter.check('u', cost=4)), (True, 0, 0.0))


class WindowBoundaryTests(unittest.TestCase):
    def test_log_prunes_event_exactly_one_window_old(self):
        log = SlidingLog()
        log.record(0.0, 1)
        log.record(3.0, 2)
        log.prune(10.0, 10.0)
        self.assertEqual(log.entries(), [(3.0, 2)])
        self.assertEqual(log.total(), 2)

    def test_check_frees_capacity_exactly_one_window_later(self):
        limiter, clock = make_limiter(2, 10)
        limiter.check('u')
        limiter.check('u')
        clock.set(10)
        self.assertEqual(summary(limiter.check('u')), (True, 1, 0.0))

    def test_peek_frees_capacity_exactly_one_window_later(self):
        limiter, clock = make_limiter(2, 10)
        limiter.check('u')
        limiter.check('u')
        clock.set(5)
        self.assertEqual(summary(limiter.peek('u')), (False, 0, 5.0))
        clock.set(10)
        self.assertEqual(summary(limiter.peek('u')), (True, 1, 0.0))
        self.assertEqual(summary(limiter.peek('u', cost=2)), (True, 0, 0.0))

    def test_peek_after_partial_expiry(self):
        limiter, clock = make_limiter(3, 10)
        limiter.check('u')
        clock.set(4)
        limiter.check('u')
        clock.set(6)
        limiter.check('u')
        clock.set(10)
        self.assertEqual(summary(limiter.peek('u')), (True, 0, 0.0))
        self.assertEqual(summary(limiter.peek('u', cost=2)), (False, 1, 4.0))
