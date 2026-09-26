import unittest

from lru import LRUCache
from sessions import SessionStore


class TestLRU(unittest.TestCase):
    def test_get_put(self):
        c = LRUCache(2)
        c.put('a', 1)
        self.assertEqual(c.get('a'), 1)
        self.assertIsNone(c.get('zz'))
        self.assertEqual(c.get('zz', 0), 0)
        self.assertEqual((c.hits, c.misses), (1, 2))

    def test_evicts_least_recent(self):
        evicted = []
        c = LRUCache(2, on_evict=lambda k, v: evicted.append((k, v)))
        c.put('a', 1)
        c.put('b', 2)
        c.get('a')
        c.put('c', 3)
        self.assertEqual(evicted, [('b', 2)])
        self.assertEqual(c.keys(), ['a', 'c'])

    def test_update_below_capacity(self):
        c = LRUCache(3)
        c.put('a', 1)
        c.put('b', 2)
        c.put('a', 10)
        self.assertEqual(c.keys(), ['b', 'a'])
        self.assertEqual(c.get('a'), 10)

    def test_invalid_capacity(self):
        with self.assertRaises(ValueError):
            LRUCache(0)


class TestSessions(unittest.TestCase):
    def test_oldest_session_expires(self):
        s = SessionStore(2)
        s.touch('u1', {})
        s.touch('u2', {})
        s.touch('u3', {})
        self.assertEqual(s.expired, ['u1'])
        self.assertEqual(s.active(), ['u2', 'u3'])
        self.assertIsNone(s.get('u1'))


if __name__ == '__main__':
    unittest.main()
