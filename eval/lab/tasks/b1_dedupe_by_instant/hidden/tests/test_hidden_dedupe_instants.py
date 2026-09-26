import unittest

from sync.records import dedupe_latest


def row(id_, ts, v, **extra):
    return {"id": id_, "updated_at": ts, "v": v, **extra}


def values(rows, **kwargs):
    return [r["v"] for r in dedupe_latest(rows, **kwargs)]


class DedupeInstantTest(unittest.TestCase):
    def test_offsets_compared_as_instants(self):
        rows = [
            row(1, "2024-01-01T12:00:00+02:00", "ten-utc"),
            row(1, "2024-01-01T11:00:00Z", "eleven-utc"),
        ]
        self.assertEqual(values(rows), ["eleven-utc"])

    def test_negative_offset(self):
        rows = [
            row(1, "2024-01-01T20:00:00-05:00", "late"),  # 01:00Z next day
            row(1, "2024-01-01T23:00:00Z", "earlier"),
        ]
        self.assertEqual(values(rows), ["late"])

    def test_naive_timestamps_are_utc(self):
        rows = [
            row(1, "2024-01-01T11:30:00", "naive"),
            row(1, "2024-01-01T12:00:00+01:00", "aware"),  # 11:00Z
        ]
        self.assertEqual(values(rows), ["naive"])
        self.assertEqual(values(list(reversed(rows))), ["naive"])

    def test_tie_keeps_later_row(self):
        rows = [
            row(1, "2024-01-01T10:00:00Z", "first"),
            row(1, "2024-01-01T11:00:00+01:00", "second"),
        ]
        self.assertEqual(values(rows), ["second"])
        same = [row(7, "2024-01-01T10:00:00Z", "a"), row(7, "2024-01-01T10:00:00Z", "b")]
        self.assertEqual(values(same), ["b"])

    def test_fractional_seconds(self):
        rows = [
            row(1, "2024-01-01T10:00:00.500Z", "half"),
            row(1, "2024-01-01T10:00:00Z", "whole"),
        ]
        self.assertEqual(values(rows), ["half"])

    def test_order_of_first_appearance(self):
        rows = [
            row("a", "2024-01-01T10:00:00Z", "a1"),
            row("b", "2024-01-01T10:00:00Z", "b1"),
            row("c", "2024-01-01T10:00:00Z", "c1"),
            row("a", "2024-01-02T10:00:00+05:00", "a2"),
            row("b", "2023-12-31T10:00:00Z", "b0"),
        ]
        self.assertEqual(values(rows), ["a2", "b1", "c1"])

    def test_custom_key_and_ts_field(self):
        rows = [
            {"sku": "X", "modified": "2024-03-01T08:00:00+00:00", "v": 1},
            {"sku": "X", "modified": "2024-03-01T09:00:00+02:00", "v": 2},  # 07:00Z
        ]
        self.assertEqual([r["v"] for r in dedupe_latest(rows, key="sku", ts_field="modified")], [1])

    def test_rows_returned_unchanged(self):
        original = row(1, "2024-01-01T10:00:00Z", "x", extra=True)
        self.assertIs(dedupe_latest([original])[0], original)

    def test_empty(self):
        self.assertEqual(dedupe_latest([]), [])


if __name__ == "__main__":
    unittest.main()
