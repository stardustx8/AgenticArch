import unittest
from datetime import timezone

from sync.loader import load_rows
from sync.records import dedupe_latest
from sync.timeparse import parse_ts


class SyncTest(unittest.TestCase):
    def test_parse_ts_z(self):
        ts = parse_ts("2024-01-01T10:00:00Z")
        self.assertEqual(ts.tzinfo, timezone.utc)
        self.assertEqual(ts.hour, 10)

    def test_dedupe_keeps_latest(self):
        rows = [
            {"id": 1, "updated_at": "2024-01-01T10:00:00Z", "v": "old"},
            {"id": 2, "updated_at": "2024-01-01T09:00:00Z", "v": "only"},
            {"id": 1, "updated_at": "2024-01-01T12:00:00Z", "v": "new"},
        ]
        result = dedupe_latest(rows)
        self.assertEqual({r["id"]: r["v"] for r in result}, {1: "new", 2: "only"})

    def test_load_rows(self):
        self.assertEqual(load_rows('[{"id": 1}]'), [{"id": 1}])
        with self.assertRaises(ValueError):
            load_rows('{"id": 1}')


if __name__ == "__main__":
    unittest.main()
