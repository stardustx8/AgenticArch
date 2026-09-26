import unittest

from ratelimit import FakeClock, RateLimiter, RateLimitMiddleware


def make_handler(calls):
    def handler(request):
        calls.append(request)
        return 200, {"Content-Type": "application/json"}, {"ok": True}

    return handler


class MiddlewareTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.calls = []

    def test_passes_through_and_reports_remaining(self):
        limiter = RateLimiter(2, 1.0, clock=self.clock)
        app = RateLimitMiddleware(make_handler(self.calls), limiter)
        status, headers, body = app({"client_ip": "10.0.0.1"})
        self.assertEqual(status, 200)
        self.assertEqual(body, {"ok": True})
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertEqual(headers["X-RateLimit-Remaining"], "1")

    def test_rejects_with_429_when_limited(self):
        limiter = RateLimiter(1, 1.0, clock=self.clock)
        app = RateLimitMiddleware(make_handler(self.calls), limiter)
        app({"client_ip": "10.0.0.1"})
        status, headers, _ = app({"client_ip": "10.0.0.1"})
        self.assertEqual(status, 429)
        self.assertEqual(headers["X-RateLimit-Remaining"], "0")
        self.assertEqual(len(self.calls), 1)

    def test_custom_key_func(self):
        limiter = RateLimiter(1, 1.0, clock=self.clock)
        app = RateLimitMiddleware(make_handler(self.calls), limiter, key_func=lambda r: r["user"])
        self.assertEqual(app({"user": "ann"})[0], 200)
        self.assertEqual(app({"user": "bob"})[0], 200)
        self.assertEqual(app({"user": "ann"})[0], 429)


if __name__ == "__main__":
    unittest.main()
