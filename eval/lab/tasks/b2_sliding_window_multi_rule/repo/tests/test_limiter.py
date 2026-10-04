import unittest

from ratelimit import FakeClock, RateLimiter


class RateLimiterTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def test_allows_up_to_limit(self):
        limiter = RateLimiter(3, 1.0, clock=self.clock)
        results = [limiter.allow("a") for _ in range(4)]
        self.assertEqual(results, [True, True, True, False])

    def test_keys_are_independent(self):
        limiter = RateLimiter(1, 1.0, clock=self.clock)
        self.assertTrue(limiter.allow("a"))
        self.assertFalse(limiter.allow("a"))
        self.assertTrue(limiter.allow("b"))

    def test_allowed_again_after_window(self):
        limiter = RateLimiter(2, 1.0, clock=self.clock)
        limiter.allow("a")
        limiter.allow("a")
        self.assertFalse(limiter.allow("a"))
        self.clock.advance(1.0)
        self.assertTrue(limiter.allow("a"))

    def test_remaining_counts_down(self):
        limiter = RateLimiter(3, 10.0, clock=self.clock)
        self.assertEqual(limiter.remaining("a"), 3)
        limiter.allow("a")
        self.assertEqual(limiter.remaining("a"), 2)

    def test_reset_clears_key(self):
        limiter = RateLimiter(1, 60.0, clock=self.clock)
        limiter.allow("a")
        limiter.reset("a")
        self.assertTrue(limiter.allow("a"))

    def test_rejects_bad_config(self):
        with self.assertRaises(ValueError):
            RateLimiter(0, 1.0, clock=self.clock)
        with self.assertRaises(ValueError):
            RateLimiter(1, 0, clock=self.clock)


if __name__ == "__main__":
    unittest.main()
