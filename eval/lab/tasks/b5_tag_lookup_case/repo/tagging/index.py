class TagIndex:
    """Many-to-many index between items and tags.

    Tags are case-insensitive and surrounding whitespace is ignored.
    """

    def __init__(self):
        self._items_by_tag = {}
        self._tags_by_item = {}

    @staticmethod
    def _normalize(tag):
        return tag.strip().lower()

    def add(self, item, *tags):
        for tag in tags:
            key = self._normalize(tag)
            if not key:
                continue
            self._items_by_tag.setdefault(key, set()).add(item)
            self._tags_by_item.setdefault(item, set()).add(key)

    def find(self, tag):
        """Items carrying ``tag``, sorted."""
        return sorted(self._items_by_tag.get(tag, ()))

    def find_all(self, *tags):
        """Items carrying every one of ``tags``, sorted."""
        if not tags:
            return []
        sets = [self._items_by_tag.get(self._normalize(tag), set()) for tag in tags]
        return sorted(set.intersection(*sets))

    def count(self, tag):
        return len(self._items_by_tag.get(tag, ()))

    def tags_of(self, item):
        return sorted(self._tags_by_item.get(item, ()))

    def remove_tag(self, item, tag):
        """Detach ``tag`` from ``item``.  Returns True if something was removed."""
        items = self._items_by_tag.get(tag)
        if not items or item not in items:
            return False
        items.discard(item)
        if not items:
            del self._items_by_tag[tag]
        tags = self._tags_by_item[item]
        tags.discard(tag)
        if not tags:
            del self._tags_by_item[item]
        return True

    def popular(self, limit=3):
        """Most used tags as (tag, count), ties broken alphabetically."""
        ranked = sorted(self._items_by_tag.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        return [(tag, len(items)) for tag, items in ranked[:limit]]
