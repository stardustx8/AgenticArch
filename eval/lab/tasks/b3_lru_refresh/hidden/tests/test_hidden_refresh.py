import unittest

from lru import LRUCache
from sessions import SessionStore


class TestUpdateAtCapacity(unittest.TestCase):
    def setUp(self):
        self.evicted = []
        self.cache = LRUCache(2, on_evict=lambda k, v: self.evicted.append(k))

    def test_update_most_recent_key_when_full(self):
        self.cache.put('a', 1)
        self.cache.put('b', 2)
        self.cache.put('b', 20)
        self.assertEqual(self.evicted, [])
        self.assertEqual(self.cache.keys(), ['a', 'b'])
        self.assertEqual(self.cache.get('a'), 1)
        self.assertEqual(self.cache.get('b'), 20)

    def test_update_least_recent_key_when_full(self):
        self.cache.put('a', 1)
        self.cache.put('b', 2)
        self.cache.put('a', 10)
        self.assertEqual(self.evicted, [])
        self.assertEqual(self.cache.keys(), ['b', 'a'])
        self.assertEqual(len(self.cache), 2)

    def test_updated_key_counts_as_recent(self):
        self.cache.put('a', 1)
        self.cache.put('b', 2)
        self.cache.put('a', 10)
        self.cache.put('c', 3)
        self.assertEqual(self.evicted, ['b'])
        self.assertEqual(self.cache.keys(), ['a', 'c'])
        self.assertEqual(self.cache.get('a'), 10)

    def test_update_does_not_touch_stats(self):
        self.cache.put('a', 1)
        self.cache.put('a', 2)
        self.assertEqual((self.cache.hits, self.cache.misses), (0, 0))

    def test_capacity_one(self):
        evicted = []
        c = LRUCache(1, on_evict=lambda k, v: evicted.append((k, v)))
        c.put('a', 1)
        c.put('a', 2)
        self.assertEqual(evicted, [])
        self.assertEqual(c.get('a'), 2)
        c.put('b', 3)
        self.assertEqual(evicted, [('a', 2)])
        self.assertEqual(c.keys(), ['b'])


class TestSessionStoreRefresh(unittest.TestCase):
    def test_retouch_keeps_everyone_logged_in(self):
        s = SessionStore(3)
        for sid in ['u1', 'u2', 'u3']:
            s.touch(sid, {'n': 0})
        s.touch('u1', {'n': 1})
        s.touch('u3', {'n': 1})
        self.assertEqual(s.expired, [])
        self.assertEqual(s.active(), ['u2', 'u1', 'u3'])
        self.assertEqual(s.get('u1'), {'n': 1})

    def test_retouched_session_survives_next_login(self):
        s = SessionStore(2)
        s.touch('u1', {})
        s.touch('u2', {})
        s.touch('u1', {'fresh': True})
        s.touch('u3', {})
        self.assertEqual(s.expired, ['u2'])
        self.assertEqual(s.get('u1'), {'fresh': True})
        self.assertIsNone(s.get('u2'))


if __name__ == '__main__':
    unittest.main()
