import unittest

from throttle import BucketRegistry, FakeClock, TokenBucket


class FractionalRefillTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def drained_bucket(self, capacity=2, rate=2.0):
        bucket = TokenBucket(capacity, rate, clock=self.clock)
        self.assertTrue(bucket.try_acquire(capacity))
        return bucket

    def test_quarter_second_polling_gets_token_back(self):
        bucket = self.drained_bucket()
        self.clock.advance(0.25)
        self.assertFalse(bucket.try_acquire())
        self.clock.advance(0.25)
        self.assertTrue(bucket.try_acquire())

    def test_steady_polling_matches_refill_rate(self):
        bucket = self.drained_bucket()
        granted = 0
        for _ in range(16):
            self.clock.advance(0.25)
            if bucket.try_acquire():
                granted += 1
        self.assertEqual(granted, 8)

    def test_many_tiny_steps_accumulate(self):
        bucket = self.drained_bucket(capacity=1, rate=4.0)
        for _ in range(15):
            self.clock.advance(0.015625)
            bucket.available()
            self.assertFalse(bucket.try_acquire())
        self.clock.advance(0.015625)
        self.assertTrue(bucket.try_acquire())

    def test_available_reports_fractional_tokens(self):
        bucket = self.drained_bucket()
        self.clock.advance(0.25)
        self.assertAlmostEqual(bucket.available(), 0.5)
        self.clock.advance(0.5)
        self.assertAlmostEqual(bucket.available(), 1.5)

    def test_fractional_remainder_survives_acquire(self):
        bucket = self.drained_bucket()
        self.clock.advance(0.75)
        self.assertTrue(bucket.try_acquire())
        self.assertAlmostEqual(bucket.available(), 0.5)
        self.clock.advance(0.25)
        self.assertTrue(bucket.try_acquire())
        self.assertFalse(bucket.try_acquire())

    def test_failed_acquire_does_not_consume(self):
        bucket = self.drained_bucket(capacity=4, rate=2.0)
        self.clock.advance(0.75)
        self.assertFalse(bucket.try_acquire(2))
        self.assertAlmostEqual(bucket.available(), 1.5)
        self.clock.advance(0.25)
        self.assertTrue(bucket.try_acquire(2))
        self.assertAlmostEqual(bucket.available(), 0.0)

    def test_long_idle_is_capped_without_banking(self):
        bucket = TokenBucket(3, 2.0, clock=self.clock)
        self.assertTrue(bucket.try_acquire())
        self.clock.advance(0.25)
        self.clock.advance(1000.0)
        self.assertAlmostEqual(bucket.available(), 3)
        self.assertTrue(bucket.try_acquire(3))
        self.assertFalse(bucket.try_acquire())
        self.clock.advance(0.25)
        self.assertAlmostEqual(bucket.available(), 0.5)

    def test_time_until_accounts_for_partial_tokens(self):
        bucket = self.drained_bucket()
        self.clock.advance(0.25)
        self.assertAlmostEqual(bucket.time_until(1), 0.25)
        self.clock.advance(0.25)
        self.assertAlmostEqual(bucket.time_until(1), 0.0)
        self.assertTrue(bucket.try_acquire())

    def test_full_bucket_allows_exactly_capacity(self):
        bucket = TokenBucket(3, 2.0, clock=self.clock)
        self.assertTrue(bucket.try_acquire(3))
        self.clock.advance(1.5)
        self.assertTrue(bucket.try_acquire(3))


class AcquireValidationTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def test_zero_tokens_rejected(self):
        bucket = TokenBucket(3, 1.0, clock=self.clock)
        with self.assertRaises(ValueError):
            bucket.try_acquire(0)

    def test_more_than_capacity_rejected_even_when_full(self):
        bucket = TokenBucket(3, 1.0, clock=self.clock)
        with self.assertRaises(ValueError):
            bucket.try_acquire(4)

    def test_invalid_requests_leave_bucket_untouched(self):
        bucket = TokenBucket(3, 1.0, clock=self.clock)
        for n in (0, -2, 4):
            with self.subTest(n=n):
                with self.assertRaises(ValueError):
                    bucket.try_acquire(n)
        self.assertEqual(bucket.available(), 3)
        self.assertTrue(bucket.try_acquire(3))


class RegistryRefillTests(unittest.TestCase):
    def test_registry_buckets_refill_fractionally(self):
        clock = FakeClock()
        registry = BucketRegistry(2, 2.0, clock=clock)
        self.assertTrue(registry.try_acquire("alice", 2))
        clock.advance(0.25)
        self.assertFalse(registry.try_acquire("alice"))
        clock.advance(0.25)
        self.assertTrue(registry.try_acquire("alice"))

    def test_registry_rejects_oversized_requests(self):
        registry = BucketRegistry(2, 2.0, clock=FakeClock())
        with self.assertRaises(ValueError):
            registry.try_acquire("alice", 3)


if __name__ == "__main__":
    unittest.main()
