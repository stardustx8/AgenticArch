import json
import unittest

from jsonflat import flatten, unflatten
from jsonflat.cli import flatten_json_text


class FlattenListsTest(unittest.TestCase):
    def test_list_of_dicts(self):
        self.assertEqual(flatten({"a": [{"b": 1}, {"b": 2}]}), {"a.0.b": 1, "a.1.b": 2})

    def test_nested_lists_and_scalars(self):
        self.assertEqual(
            flatten({"a": [1, [2, 3]], "b": {"c": [None, True]}}),
            {"a.0": 1, "a.1.0": 2, "a.1.1": 3, "b.c.0": None, "b.c.1": True},
        )

    def test_empty_containers_are_kept(self):
        self.assertEqual(
            flatten({"a": {}, "b": [], "c": {"d": [], "e": {"f": {}}}, "g": [[]]}),
            {"a": {}, "b": [], "c.d": [], "c.e.f": {}, "g.0": []},
        )

    def test_empty_document(self):
        self.assertEqual(flatten({}), {})

    def test_separator_applies_to_list_indexes(self):
        self.assertEqual(flatten({"a": [{"b": 1}]}, sep="/"), {"a/0/b": 1})

    def test_cli_with_lists(self):
        out = json.loads(flatten_json_text('{"items": [{"sku": "A"}, {"sku": "B"}], "tags": []}'))
        self.assertEqual(out, {"items.0.sku": "A", "items.1.sku": "B", "tags": []})


class UnflattenTest(unittest.TestCase):
    def test_rebuilds_lists(self):
        self.assertEqual(unflatten({"a.0.b": 1, "a.1.b": 2}), {"a": [{"b": 1}, {"b": 2}]})

    def test_list_order_follows_index_not_insertion(self):
        self.assertEqual(unflatten({"a.1": "y", "a.0": "x", "a.2": "z"}), {"a": ["x", "y", "z"]})

    def test_non_consecutive_indexes_stay_dict(self):
        self.assertEqual(unflatten({"a.0": 1, "a.2": 2}), {"a": {"0": 1, "2": 2}})
        self.assertEqual(unflatten({"a.1": 1}), {"a": {"1": 1}})

    def test_mixed_keys_stay_dict(self):
        self.assertEqual(unflatten({"a.0": 1, "a.x": 2}), {"a": {"0": 1, "x": 2}})

    def test_round_trip(self):
        docs = [
            {"user": {"name": "ann", "tags": ["x", "y"], "addresses": [{"city": "Oslo", "lines": ["1 Main St"]}]}},
            {"matrix": [[1, 2], [3, 4]], "meta": {}, "list": [], "n": None},
            {"deep": {"a": [{"b": [{"c": []}]}]}},
            {},
        ]
        for doc in docs:
            with self.subTest(doc=doc):
                self.assertEqual(unflatten(flatten(doc)), doc)

    def test_round_trip_custom_separator(self):
        doc = {"a.b": {"c": [1, 2]}}
        self.assertEqual(unflatten(flatten(doc, sep="|"), sep="|"), doc)


if __name__ == "__main__":
    unittest.main()
