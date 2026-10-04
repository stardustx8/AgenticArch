import json
import unittest

from jsonflat import flatten, unflatten
from jsonflat.cli import flatten_json_text


class FlattenTest(unittest.TestCase):
    def test_nested_dicts(self):
        doc = {"a": {"b": {"c": 1}, "d": 2}, "e": "x"}
        self.assertEqual(flatten(doc), {"a.b.c": 1, "a.d": 2, "e": "x"})

    def test_custom_separator(self):
        self.assertEqual(flatten({"a": {"b": 1}}, sep="/"), {"a/b": 1})

    def test_unflatten(self):
        self.assertEqual(unflatten({"a.b.c": 1, "a.d": 2}), {"a": {"b": {"c": 1}, "d": 2}})

    def test_cli(self):
        self.assertEqual(json.loads(flatten_json_text('{"x": {"y": null}}')), {"x.y": None})


if __name__ == "__main__":
    unittest.main()
