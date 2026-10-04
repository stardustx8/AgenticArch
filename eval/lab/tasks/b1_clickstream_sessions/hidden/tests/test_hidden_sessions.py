import json
import unittest
from datetime import datetime, timedelta, timezone

from clickstream.events import parse_events
from clickstream.report import summarize
from clickstream.sessions import sessionize

UTC = timezone.utc


def line(user, ts, action):
    return json.dumps({"user": user, "ts": ts, "action": action})


def at(hour, minute, second=0):
    return datetime(2024, 5, 1, hour, minute, second, tzinfo=UTC)


class UnsortedInputTest(unittest.TestCase):
    def test_out_of_order_events_form_one_session(self):
        events = parse_events([
            line("u1", "2024-05-01T10:20:00Z", "c"),
            line("u1", "2024-05-01T10:00:00Z", "a"),
            line("u1", "2024-05-01T10:10:00Z", "b"),
        ])
        sessions = sessionize(events)
        self.assertEqual(len(sessions), 1)
        s = sessions[0]
        self.assertEqual(s.actions, ["a", "b", "c"])
        self.assertEqual((s.start, s.end), (at(10, 0), at(10, 20)))
        self.assertEqual(s.duration_seconds, 1200)

    def test_late_event_splits_correctly(self):
        events = parse_events([
            line("u1", "2024-05-01T11:00:00Z", "late"),
            line("u1", "2024-05-01T10:00:00Z", "early"),
            line("u1", "2024-05-01T11:10:00Z", "later"),
        ])
        self.assertEqual([s.actions for s in sessionize(events)], [["early"], ["late", "later"]])

    def test_same_timestamp_keeps_input_order(self):
        events = parse_events([
            line("u1", "2024-05-01T10:00:00Z", "first"),
            line("u1", "2024-05-01T10:00:00Z", "second"),
        ])
        self.assertEqual(sessionize(events)[0].actions, ["first", "second"])

    def test_sessions_ordered_by_start_then_user(self):
        events = parse_events([
            line("u3", "2024-05-01T10:00:00Z", "x"),
            line("u1", "2024-05-01T10:00:00Z", "x"),
            line("u2", "2024-05-01T09:00:00Z", "x"),
        ])
        self.assertEqual([s.user for s in sessionize(events)], ["u2", "u1", "u3"])


class GapTest(unittest.TestCase):
    def test_exact_gap_is_same_session(self):
        events = parse_events([
            line("u1", "2024-05-01T10:00:00Z", "a"),
            line("u1", "2024-05-01T10:30:00Z", "b"),
        ])
        self.assertEqual(len(sessionize(events)), 1)

    def test_just_over_gap_splits(self):
        events = parse_events([
            line("u1", "2024-05-01T10:00:00Z", "a"),
            line("u1", "2024-05-01T10:30:01Z", "b"),
        ])
        self.assertEqual(len(sessionize(events)), 2)

    def test_custom_gap(self):
        events = parse_events([
            line("u1", "2024-05-01T10:00:00Z", "a"),
            line("u1", "2024-05-01T10:05:00Z", "b"),
            line("u1", "2024-05-01T10:11:00Z", "c"),
        ])
        self.assertEqual([s.actions for s in sessionize(events, gap_minutes=5)], [["a", "b"], ["c"]])


class TimezoneTest(unittest.TestCase):
    def test_offsets_normalised_to_utc(self):
        events = parse_events([
            line("u1", "2024-05-01T12:00:00+02:00", "a"),
            line("u1", "2024-05-01T10:25:00Z", "b"),
            line("u1", "2024-05-01T06:40:00-04:00", "c"),
        ])
        for ev in events:
            self.assertEqual(ev.ts.utcoffset(), timedelta(0))
        self.assertEqual(events[0].ts, at(10, 0))
        sessions = sessionize(events)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].actions, ["a", "b", "c"])
        self.assertEqual((sessions[0].start, sessions[0].end), (at(10, 0), at(10, 40)))

    def test_offset_ordering_across_users(self):
        events = parse_events([
            line("a", "2024-05-01T10:30:00+01:00", "x"),  # 09:30Z
            line("b", "2024-05-01T10:00:00Z", "x"),
        ])
        self.assertEqual([s.user for s in sessionize(events)], ["a", "b"])


class MalformedLinesTest(unittest.TestCase):
    LINES = [
        "{not json",
        line("u1", "2024-05-01T10:00:00Z", "ok"),
        "",
        json.dumps({"user": "u1", "action": "no-ts"}),
        line("u1", "yesterday", "bad-ts"),
        "42",
        json.dumps({"user": "u2", "ts": 1714557600, "action": "numeric-ts"}),
        line("u2", "2024-05-01T10:01:00+00:00", "ok2"),
        "   ",
    ]

    def test_malformed_lines_skipped(self):
        self.assertEqual([e.action for e in parse_events(self.LINES)], ["ok", "ok2"])

    def test_error_line_numbers_collected(self):
        errors = []
        parse_events(self.LINES, errors=errors)
        self.assertEqual(errors, [1, 4, 5, 6, 7])

    def test_summary_after_cleanup(self):
        stats = summarize(sessionize(parse_events(self.LINES)))
        self.assertEqual(stats, {
            "u1": {"sessions": 1, "actions": 1, "seconds": 0},
            "u2": {"sessions": 1, "actions": 1, "seconds": 0},
        })


if __name__ == "__main__":
    unittest.main()
