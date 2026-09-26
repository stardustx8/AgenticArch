import unittest

from cachekit import FakeClock, LRUCache


class LRUCacheTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.cache = LRUCache(3, clock=self.clock)

    def test_get_set_roundtrip(self):
        self.cache.set("a", 1)
        self.assertEqual(self.cache.get("a"), 1)
        self.assertIn("a", self.cache)
        self.assertEqual(len(self.cache), 1)

    def test_missing_returns_default(self):
        self.assertIsNone(self.cache.get("nope"))
        self.assertEqual(self.cache.get("nope", 42), 42)
        self.assertNotIn("nope", self.cache)

    def test_evicts_least_recently_used(self):
        for k in "abc":
            self.cache.set(k, k.upper())
        self.cache.get("a")
        self.cache.set("d", "D")
        self.assertNotIn("b", self.cache)
        self.assertEqual(self.cache.keys(), ["c", "a", "d"])

    def test_set_existing_key_updates_without_evicting(self):
        for k in "abc":
            self.cache.set(k, 0)
        self.cache.set("a", 99)
        self.assertEqual(len(self.cache), 3)
        self.assertEqual(self.cache.get("a"), 99)
        self.assertEqual(self.cache.keys(), ["b", "c", "a"])

    def test_delete(self):
        self.cache.set("a", 1)
        self.assertTrue(self.cache.delete("a"))
        self.assertFalse(self.cache.delete("a"))
        self.assertEqual(len(self.cache), 0)

    def test_capacity_must_be_positive(self):
        with self.assertRaises(ValueError):
            LRUCache(0)
