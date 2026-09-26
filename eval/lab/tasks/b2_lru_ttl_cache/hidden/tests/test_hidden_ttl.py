import unittest

from cachekit import FakeClock, LRUCache


class TTLTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()

    def make(self, capacity=4, **kwargs):
        return LRUCache(capacity, clock=self.clock, **kwargs)

    def test_entry_expires_when_ttl_elapses(self):
        cache = self.make()
        cache.set("a", 1, ttl=10)
        self.clock.advance(9.5)
        self.assertIn("a", cache)
        self.clock.advance(0.5)
        self.assertIsNone(cache.get("a"))

    def test_expired_entry_is_not_contained_or_counted(self):
        cache = self.make()
        cache.set("a", 1, ttl=5)
        cache.set("b", 2)
        self.assertEqual(len(cache), 2)
        self.clock.advance(5)
        self.assertNotIn("a", cache)
        self.assertIn("b", cache)
        self.assertEqual(len(cache), 1)
        self.assertEqual(cache.keys(), ["b"])

    def test_expired_get_returns_supplied_default(self):
        cache = self.make()
        cache.set("a", 1, ttl=5)
        self.clock.advance(6)
        self.assertEqual(cache.get("a", "fallback"), "fallback")

    def test_expired_get_counts_as_miss(self):
        cache = self.make()
        cache.set("a", 1, ttl=5)
        cache.get("a")
        self.clock.advance(5)
        cache.get("a")
        self.assertEqual(cache.stats.hits, 1)
        self.assertEqual(cache.stats.misses, 1)

    def test_expired_entry_stays_gone(self):
        cache = self.make()
        cache.set("a", 1, ttl=5)
        self.clock.advance(5)
        self.assertIsNone(cache.get("a"))
        self.assertIsNone(cache.get("a"))
        self.assertNotIn("a", cache)
        self.assertEqual(len(cache), 0)
        cache.set("a", 2, ttl=5)
        self.assertEqual(cache.get("a"), 2)

    def test_default_ttl_applies_when_set_has_no_ttl(self):
        cache = self.make(default_ttl=10)
        cache.set("a", 1)
        self.clock.advance(9)
        self.assertIn("a", cache)
        self.clock.advance(1)
        self.assertNotIn("a", cache)

    def test_explicit_ttl_overrides_default(self):
        cache = self.make(default_ttl=10)
        cache.set("short", 1, ttl=2)
        cache.set("long", 2, ttl=100)
        cache.set("plain", 3)
        self.clock.advance(2)
        self.assertNotIn("short", cache)
        self.assertIn("plain", cache)
        self.clock.advance(8)
        self.assertNotIn("plain", cache)
        self.assertEqual(cache.get("long"), 2)

    def test_default_ttl_none_never_expires(self):
        cache = self.make(default_ttl=None)
        cache.set("a", 1)
        self.clock.advance(10**6)
        self.assertEqual(cache.get("a"), 1)

    def test_resetting_key_refreshes_expiry(self):
        cache = self.make()
        cache.set("a", 1, ttl=10)
        self.clock.advance(6)
        cache.set("a", 2, ttl=10)
        self.assertEqual(cache.get("a"), 2)
        self.clock.advance(6)
        self.assertIn("a", cache)
        self.clock.advance(4)
        self.assertNotIn("a", cache)

    def test_resetting_key_without_ttl_removes_expiry(self):
        cache = self.make()
        cache.set("a", 1, ttl=5)
        cache.set("a", 2)
        self.clock.advance(100)
        self.assertEqual(cache.get("a"), 2)

    def test_non_positive_ttl_rejected(self):
        cache = self.make()
        for bad in (0, -1, -0.5):
            with self.subTest(ttl=bad):
                with self.assertRaises(ValueError):
                    cache.set("a", 1, ttl=bad)
        self.assertNotIn("a", cache)
        self.assertEqual(len(cache), 0)
        for bad in (0, -3):
            with self.subTest(default_ttl=bad):
                with self.assertRaises(ValueError):
                    self.make(default_ttl=bad)

    def test_full_cache_drops_expired_before_evicting_live(self):
        cache = self.make(capacity=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3, ttl=5)
        self.clock.advance(5)
        cache.set("d", 4)
        for key in ("a", "b", "d"):
            self.assertIn(key, cache)
        self.assertNotIn("c", cache)
        self.assertEqual(len(cache), 3)

    def test_multiple_expired_entries_make_room(self):
        cache = self.make(capacity=3)
        cache.set("live", 0)
        cache.set("x", 1, ttl=5)
        cache.set("y", 2, ttl=5)
        self.clock.advance(5)
        cache.set("d", 3)
        cache.set("e", 4)
        self.assertEqual(cache.keys(), ["live", "d", "e"])

    def test_lru_eviction_among_live_entries(self):
        cache = self.make(capacity=3, default_ttl=100)
        for key in "abc":
            cache.set(key, key.upper())
        self.clock.advance(1)
        cache.get("a")
        cache.set("d", "D")
        self.assertNotIn("b", cache)
        self.assertEqual(cache.keys(), ["c", "a", "d"])

    def test_keys_skip_expired_and_keep_order(self):
        cache = self.make()
        cache.set("a", 1)
        cache.set("b", 2, ttl=5)
        cache.set("c", 3)
        cache.get("a")
        self.clock.advance(5)
        self.assertEqual(cache.keys(), ["c", "a"])
