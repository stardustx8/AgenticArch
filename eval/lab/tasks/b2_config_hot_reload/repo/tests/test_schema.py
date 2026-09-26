import unittest

from livecfg import Field, flatten, lookup, validate

SCHEMA = {"db.host": Field(str), "db.port": Field(int), "debug": Field(bool, required=False)}


class ValidateTests(unittest.TestCase):
    def test_valid_config_has_no_problems(self):
        self.assertEqual(validate({"db": {"host": "h", "port": 1}}, SCHEMA), [])

    def test_missing_required_key(self):
        self.assertEqual(validate({"db": {"port": 1}}, SCHEMA), ["db.host: required"])

    def test_wrong_types_reported(self):
        problems = validate({"db": {"host": "h", "port": True}, "debug": "yes"}, SCHEMA)
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("db.port"))
        self.assertTrue(problems[1].startswith("debug"))

    def test_non_object_config(self):
        self.assertEqual(len(validate([1, 2], SCHEMA)), 1)


class FlattenTests(unittest.TestCase):
    def test_flatten_nested_dicts(self):
        tree = {"a": {"b": 1, "c": [1, 2]}, "d": "x", "e": {}}
        self.assertEqual(flatten(tree), {"a.b": 1, "a.c": [1, 2], "d": "x"})

    def test_lookup(self):
        tree = {"a": {"b": {"c": 3}}}
        self.assertEqual(lookup(tree, "a.b.c"), 3)
        with self.assertRaises(KeyError):
            lookup(tree, "a.x")


if __name__ == "__main__":
    unittest.main()
