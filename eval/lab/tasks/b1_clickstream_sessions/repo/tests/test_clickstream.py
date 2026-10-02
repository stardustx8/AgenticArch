import json
import unittest

from clickstream.events import parse_events
from clickstream.report import summarize
from clickstream.sessions import sessionize


def line(user, ts, action):
    return json.dumps({"user": user, "ts": ts, "action": action})


LINES = [
    line("u1", "2024-05-01T10:00:00Z", "view"),
    line("u2", "2024-05-01T10:01:00Z", "view"),
    line("u1", "2024-05-01T10:05:00Z", "click"),
    "",
    line("u1", "2024-05-01T11:00:00Z", "view"),
]


class ClickstreamTest(unittest.TestCase):
    def test_parse(self):
        events = parse_events(LINES)
        self.assertEqual(len(events), 4)
        self.assertEqual(events[0].user, "u1")
        self.assertEqual((events[0].ts.hour, events[0].ts.minute), (10, 0))

    def test_sessionize(self):
        sessions = sessionize(parse_events(LINES))
        self.assertEqual(
            [(s.user, s.actions) for s in sessions],
            [("u1", ["view", "click"]), ("u2", ["view"]), ("u1", ["view"])],
        )

    def test_summary(self):
        stats = summarize(sessionize(parse_events(LINES)))
        self.assertEqual(stats["u1"], {"sessions": 2, "actions": 3, "seconds": 300})
        self.assertEqual(stats["u2"], {"sessions": 1, "actions": 1, "seconds": 0})


if __name__ == "__main__":
    unittest.main()
