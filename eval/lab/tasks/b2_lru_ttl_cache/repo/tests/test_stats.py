import unittest

from cachekit import CacheStats, FakeClock, LRUCache


class StatsTests(unittest.TestCase):
    def test_hits_and_misses_recorded_with_clock_time(self):
        clock = FakeClock(start=100.0)
        cache = LRUCache(2, clock=clock)
        cache.set("a", 1)
        cache.get("a")
        clock.advance(2.5)
        cache.get("b")
        self.assertEqual(cache.stats.hits, 1)
        self.assertEqual(cache.stats.misses, 1)
        self.assertEqual(cache.stats.last_access, 102.5)
        self.assertEqual(cache.stats.hit_rate, 0.5)

    def test_evictions_counted(self):
        cache = LRUCache(1, clock=FakeClock())
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("b", 3)
        self.assertEqual(cache.stats.evictions, 1)

    def test_empty_stats(self):
        stats = CacheStats()
        self.assertEqual(stats.lookups, 0)
        self.assertEqual(stats.hit_rate, 0.0)

    def test_fake_clock_rejects_going_backwards(self):
        clock = FakeClock(5)
        clock.advance(1)
        self.assertEqual(clock(), 6)
        with self.assertRaises(ValueError):
            clock.advance(-1)
