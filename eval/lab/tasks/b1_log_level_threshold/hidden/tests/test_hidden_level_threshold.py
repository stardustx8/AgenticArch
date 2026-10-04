import unittest

from logtool.filters import filter_by_level
from logtool.parser import LogEntry, parse_lines


def entry(level, msg):
    return LogEntry("2024-03-01 12:00:00", level, msg)


def msgs(entries):
    return [e.message for e in entries]


class LevelThresholdTest(unittest.TestCase):
    def setUp(self):
        self.entries = [
            entry("DEBUG", "d"),
            entry("INFO", "i"),
            entry("WARNING", "w"),
            entry("ERROR", "e"),
            entry("CRITICAL", "c"),
        ]

    def test_min_level_includes_more_severe(self):
        self.assertEqual(msgs(filter_by_level(self.entries, "DEBUG")), ["d", "i", "w", "e", "c"])
        self.assertEqual(msgs(filter_by_level(self.entries, "INFO")), ["i", "w", "e", "c"])
        self.assertEqual(msgs(filter_by_level(self.entries, "ERROR")), ["e", "c"])
        self.assertEqual(msgs(filter_by_level(self.entries, "CRITICAL")), ["c"])

    def test_min_level_case_insensitive_and_aliases(self):
        self.assertEqual(msgs(filter_by_level(self.entries, "warning")), ["w", "e", "c"])
        self.assertEqual(msgs(filter_by_level(self.entries, "Warn")), ["w", "e", "c"])
        self.assertEqual(msgs(filter_by_level(self.entries, "fatal")), ["c"])

    def test_entry_levels_aliases_and_case(self):
        entries = [entry("warn", "w1"), entry("Fatal", "f1"), entry("info", "i1"), entry("error", "e1"), entry("debug", "d1")]
        self.assertEqual(msgs(filter_by_level(entries, "WARNING")), ["w1", "f1", "e1"])
        self.assertEqual(msgs(filter_by_level(entries, "CRITICAL")), ["f1"])

    def test_unknown_entry_levels_dropped(self):
        entries = [entry("TRACE", "t"), entry("NOTICE", "n"), entry("INFO", "i")]
        self.assertEqual(msgs(filter_by_level(entries, "DEBUG")), ["i"])

    def test_unknown_min_level_raises(self):
        with self.assertRaises(ValueError):
            filter_by_level(self.entries, "VERBOSE")
        with self.assertRaises(ValueError):
            filter_by_level([], "")

    def test_parsed_lines_with_aliases(self):
        lines = [
            "2024-03-01 12:00:00 [WARN] disk 91%\n",
            "2024-03-01 12:00:01 [info] heartbeat\n",
            "2024-03-01 12:00:02 [FATAL] out of memory\n",
        ]
        self.assertEqual(msgs(filter_by_level(parse_lines(lines), "warning")), ["disk 91%", "out of memory"])

    def test_accepts_iterator_returns_list(self):
        result = filter_by_level(iter(self.entries), "INFO")
        self.assertIsInstance(result, list)
        self.assertEqual(msgs(result), ["i", "w", "e", "c"])


if __name__ == "__main__":
    unittest.main()
