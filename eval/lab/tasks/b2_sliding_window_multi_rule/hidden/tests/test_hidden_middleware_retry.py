import unittest

import ratelimit.limiter as rl
from ratelimit import FakeClock, RateLimitMiddleware


class RetryAfterHeaderTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.calls = []

    def handler(self, request):
        self.calls.append(request)
        return 200, {"Content-Type": "application/json"}, {"ok": True}

    def call(self, app):
        return app({"client_ip": "10.0.0.1"})

    def test_429_includes_retry_after(self):
        app = RateLimitMiddleware(self.handler, rl.RateLimiter(1, 1.0, clock=self.clock))
        self.assertEqual(self.call(app)[0], 200)
        self.clock.advance(0.75)
        status, headers, _ = self.call(app)
        self.assertEqual(status, 429)
        self.assertEqual(float(headers["Retry-After"]), 1.0)
        self.assertEqual(len(self.calls), 1)

    def test_fractional_wait_rounds_up(self):
        app = RateLimitMiddleware(self.handler, rl.RateLimiter(1, 2.0, clock=self.clock))
        self.call(app)
        self.clock.advance(0.5)
        status, headers, _ = self.call(app)
        self.assertEqual(status, 429)
        self.assertEqual(float(headers["Retry-After"]), 2.0)

    def test_whole_second_wait_is_not_inflated(self):
        app = RateLimitMiddleware(self.handler, rl.RateLimiter(1, 3.0, clock=self.clock))
        self.call(app)
        self.clock.advance(1.0)
        status, headers, _ = self.call(app)
        self.assertEqual(status, 429)
        self.assertEqual(float(headers["Retry-After"]), 2.0)

    def test_multi_rule_limiter_reports_longest_wait(self):
        limiter = rl.RateLimiter(rules=[rl.Rule(1, 1.0), rl.Rule(2, 10.0)], clock=self.clock)
        app = RateLimitMiddleware(self.handler, limiter)
        self.assertEqual(self.call(app)[0], 200)
        self.clock.advance(1.0)
        self.assertEqual(self.call(app)[0], 200)
        self.clock.advance(1.0)
        status, headers, _ = self.call(app)
        self.assertEqual(status, 429)
        self.assertEqual(float(headers["Retry-After"]), 8.0)
        self.assertEqual(len(self.calls), 2)


if __name__ == "__main__":
    unittest.main()
