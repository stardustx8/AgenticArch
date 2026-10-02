import unittest

from throttle import FakeClock, TokenBucket


class TokenBucketTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def test_starts_full(self):
        bucket = TokenBucket(5, 1.0, clock=self.clock)
        self.assertEqual(bucket.available(), 5)

    def test_denies_once_drained(self):
        bucket = TokenBucket(3, 1.0, clock=self.clock)
        results = [bucket.try_acquire() for _ in range(4)]
        self.assertEqual(results, [True, True, True, False])

    def test_acquire_multiple_tokens(self):
        bucket = TokenBucket(5, 1.0, clock=self.clock)
        self.assertTrue(bucket.try_acquire(3))
        self.assertFalse(bucket.try_acquire(3))
        self.assertEqual(bucket.available(), 2)

    def test_refills_after_whole_seconds(self):
        bucket = TokenBucket(4, 2.0, clock=self.clock)
        self.assertTrue(bucket.try_acquire(4))
        self.clock.advance(1.0)
        self.assertTrue(bucket.try_acquire(2))
        self.assertFalse(bucket.try_acquire())

    def test_refill_is_capped_at_capacity(self):
        bucket = TokenBucket(3, 1.0, clock=self.clock)
        bucket.try_acquire()
        self.clock.advance(100.0)
        self.assertEqual(bucket.available(), 3)

    def test_time_until(self):
        bucket = TokenBucket(2, 0.5, clock=self.clock)
        bucket.try_acquire(2)
        self.assertEqual(bucket.time_until(1), 2.0)
        self.clock.advance(2.0)
        self.assertEqual(bucket.time_until(1), 0.0)
        self.assertTrue(bucket.try_acquire())

    def test_rejects_bad_config(self):
        with self.assertRaises(ValueError):
            TokenBucket(0, 1.0, clock=self.clock)
        with self.assertRaises(ValueError):
            TokenBucket(1, 0, clock=self.clock)


if __name__ == "__main__":
    unittest.main()
