import unittest

from logtool.filters import filter_by_level, filter_by_text
from logtool.parser import parse_line, parse_lines
from logtool.report import count_by_level

SAMPLE = [
    "2024-03-01 12:00:00 [INFO] service started\n",
    "garbage line\n",
    "2024-03-01 12:00:05 [ERROR] db timeout\n",
    "2024-03-01 12:00:09 [INFO] retrying\n",
]


class ParserTest(unittest.TestCase):
    def test_parse_line(self):
        e = parse_line(SAMPLE[0])
        self.assertEqual(e.timestamp, "2024-03-01 12:00:00")
        self.assertEqual(e.level, "INFO")
        self.assertEqual(e.message, "service started")

    def test_parse_lines_skips_garbage(self):
        self.assertEqual(len(parse_lines(SAMPLE)), 3)


class FilterTest(unittest.TestCase):
    def test_filter_error(self):
        entries = parse_lines(SAMPLE)
        self.assertEqual([e.message for e in filter_by_level(entries, "ERROR")], ["db timeout"])

    def test_filter_text(self):
        self.assertEqual(len(filter_by_text(parse_lines(SAMPLE), "retry")), 1)

    def test_count(self):
        self.assertEqual(count_by_level(parse_lines(SAMPLE)), {"INFO": 2, "ERROR": 1})


if __name__ == "__main__":
    unittest.main()
