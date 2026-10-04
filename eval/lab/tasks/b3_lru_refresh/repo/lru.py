from collections import OrderedDict


class LRUCache:
    def __init__(self, capacity, on_evict=None):
        if capacity < 1:
            raise ValueError('capacity must be at least 1')
        self.capacity = capacity
        self._data = OrderedDict()
        self._on_evict = on_evict
        self.hits = 0
        self.misses = 0

    def get(self, key, default=None):
        if key in self._data:
            self.hits += 1
            self._data.move_to_end(key)
            return self._data[key]
        self.misses += 1
        return default

    def put(self, key, value):
        if len(self._data) >= self.capacity:
            old_key, old_value = self._data.popitem(last=False)
            if self._on_evict is not None:
                self._on_evict(old_key, old_value)
        self._data[key] = value
        self._data.move_to_end(key)

    def keys(self):
        # Least recently used first.
        return list(self._data)

    def __contains__(self, key):
        return key in self._data

    def __len__(self):
        return len(self._data)
