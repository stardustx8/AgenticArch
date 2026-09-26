from lru import LRUCache


class SessionStore:
    def __init__(self, capacity):
        self.expired = []
        self._cache = LRUCache(capacity, on_evict=self._expire)

    def _expire(self, session_id, data):
        self.expired.append(session_id)

    def touch(self, session_id, data):
        self._cache.put(session_id, data)

    def get(self, session_id):
        return self._cache.get(session_id)

    def active(self):
        return self._cache.keys()
