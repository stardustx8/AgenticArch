import unittest

import ratelimit.limiter as rl
from ratelimit import FakeClock


class LimiterTestCase(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def at(self, t):
        self.clock.advance(t - self.clock())


class SlidingWindowTests(LimiterTestCase):
    def test_boundary_burst_is_prevented(self):
        limiter = rl.RateLimiter(2, 1.0, clock=self.clock)
        self.at(0.75)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.at(1.25)
        self.assertFalse(limiter.allow("a"))
        self.at(1.75)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))

    def test_hit_stops_counting_exactly_at_t_plus_window(self):
        limiter = rl.RateLimiter(1, 1.0, clock=self.clock)
        self.at(0.25)
        self.assertTrue(limiter.allow("a"))
        self.at(1.0)
        self.assertFalse(limiter.allow("a"))
        self.at(1.25)
        self.assertTrue(limiter.allow("a"))

    def test_each_hit_expires_individually(self):
        limiter = rl.RateLimiter(2, 1.0, clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.at(0.5)
        self.assertTrue(limiter.allow("a"))
        self.at(0.75)
        self.assertFalse(limiter.allow("a"))
        self.at(1.0)
        self.assertTrue(limiter.allow("a"))
        self.at(1.25)
        self.assertFalse(limiter.allow("a"))
        self.at(1.5)
        self.assertTrue(limiter.allow("a"))

    def test_long_rule_can_deny_when_short_rule_allows(self):
        limiter = rl.RateLimiter(rules=[rl.Rule(2, 1.0), rl.Rule(3, 10.0)], clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.at(1.0)
        self.assertTrue(limiter.allow("a"))
        self.at(2.0)
        self.assertFalse(limiter.allow("a"))
        self.at(9.75)
        self.assertFalse(limiter.allow("a"))
        self.at(10.0)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))

    def test_denied_requests_do_not_count_against_short_rule(self):
        limiter = rl.RateLimiter(rules=[rl.Rule(2, 1.0), rl.Rule(3, 4.0)], clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.at(1.0)
        self.assertTrue(limiter.allow("a"))
        for t in (2.0, 2.5, 3.0, 3.5, 3.75):
            self.at(t)
            self.assertFalse(limiter.allow("a"))
        self.at(4.0)
        self.assertTrue(limiter.allow("a"))
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))

    def test_denied_requests_do_not_count_against_long_rule(self):
        limiter = rl.RateLimiter(rules=[rl.Rule(1, 1.0), rl.Rule(3, 10.0)], clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.at(0.5)
        for _ in range(5):
            self.assertFalse(limiter.allow("a"))
        self.at(1.0)
        self.assertTrue(limiter.allow("a"))
        self.at(2.0)
        self.assertTrue(limiter.allow("a"))
        self.at(3.0)
        self.assertFalse(limiter.allow("a"))

    def test_keys_are_independent_across_rules(self):
        limiter = rl.RateLimiter(rules=[rl.Rule(1, 1.0), rl.Rule(2, 10.0)], clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))
        self.at(1.0)
        self.assertTrue(limiter.allow("a"))
        self.at(2.0)
        self.assertFalse(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))

    def test_invalid_rules_rejected(self):
        for limit, window in [(0, 1.0), (-1, 1.0), (1, 0), (1, -0.5)]:
            with self.subTest(limit=limit, window=window):
                with self.assertRaises(ValueError):
                    rl.RateLimiter(rules=[rl.Rule(limit, window)], clock=self.clock)


class RetryAfterTests(LimiterTestCase):
    def test_zero_when_request_would_be_allowed(self):
        limiter = rl.RateLimiter(2, 1.0, clock=self.clock)
        self.assertEqual(limiter.retry_after("a"), 0.0)
        self.assertTrue(limiter.allow("a"))
        self.assertEqual(limiter.retry_after("a"), 0.0)

    def test_single_rule_waits_for_oldest_counted_hit(self):
        limiter = rl.RateLimiter(2, 1.0, clock=self.clock)
        self.at(0.25)
        self.assertTrue(limiter.allow("a"))
        self.at(0.5)
        self.assertTrue(limiter.allow("a"))
        self.at(0.75)
        self.assertAlmostEqual(limiter.retry_after("a"), 0.5)
        self.at(1.0)
        self.assertAlmostEqual(limiter.retry_after("a"), 0.25)
        self.at(1.25)
        self.assertEqual(limiter.retry_after("a"), 0.0)
        self.assertTrue(limiter.allow("a"))

    def test_uses_hit_that_must_expire_not_oldest_tracked(self):
        limiter = rl.RateLimiter(rules=[rl.Rule(2, 1.0), rl.Rule(10, 60.0)], clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.at(0.25)
        self.assertTrue(limiter.allow("a"))
        self.at(1.0)
        self.assertTrue(limiter.allow("a"))
        self.at(1.125)
        self.assertAlmostEqual(limiter.retry_after("a"), 0.125)

    def test_multiple_rules_take_the_longest_wait(self):
        limiter = rl.RateLimiter(rules=[rl.Rule(2, 1.0), rl.Rule(3, 2.0)], clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.at(0.5)
        self.assertTrue(limiter.allow("a"))
        self.at(1.25)
        self.assertTrue(limiter.allow("a"))
        self.at(1.375)
        wait = limiter.retry_after("a")
        self.assertAlmostEqual(wait, 0.625)
        self.clock.advance(wait)
        self.assertTrue(limiter.allow("a"))

    def test_retry_after_does_not_record_a_request(self):
        limiter = rl.RateLimiter(1, 1.0, clock=self.clock)
        for _ in range(5):
            self.assertEqual(limiter.retry_after("a"), 0.0)
        self.assertTrue(limiter.allow("a"))
        self.at(0.5)
        first = limiter.retry_after("a")
        self.assertAlmostEqual(first, 0.5)
        self.assertAlmostEqual(limiter.retry_after("a"), first)
        self.assertEqual(limiter.retry_after("b"), 0.0)
        self.at(1.0)
        self.assertTrue(limiter.allow("a"))

    def test_waiting_retry_after_lets_request_through(self):
        limiter = rl.RateLimiter(3, 2.0, clock=self.clock)
        for t in (0.0, 0.5, 1.0):
            self.at(t)
            self.assertTrue(limiter.allow("a"))
        self.at(1.25)
        self.assertFalse(limiter.allow("a"))
        wait = limiter.retry_after("a")
        self.assertAlmostEqual(wait, 0.75)
        self.clock.advance(wait)
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))
        self.assertAlmostEqual(limiter.retry_after("a"), 0.5)


if __name__ == "__main__":
    unittest.main()
