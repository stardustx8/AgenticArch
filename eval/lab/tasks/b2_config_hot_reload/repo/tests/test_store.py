import json
import unittest

from livecfg import ConfigError, ConfigStore, Field

SCHEMA = {"db.host": Field(str), "db.port": Field(int), "debug": Field(bool, required=False)}


class Source:
    def __init__(self, text):
        self.text = text

    def __call__(self):
        return self.text


def doc(**db):
    return json.dumps({"db": {"host": "db-1", "port": 5432, **db}})


class ConfigStoreTests(unittest.TestCase):
    def test_load_and_get_dotted_keys(self):
        store = ConfigStore(Source(doc()), SCHEMA)
        store.load()
        self.assertTrue(store.loaded)
        self.assertEqual(store.get("db.port"), 5432)
        self.assertEqual(store.get("db.nope", 7), 7)
        self.assertIsNone(store.get("db.host.deeper"))

    def test_get_before_load_returns_default(self):
        store = ConfigStore(Source(doc()), SCHEMA)
        self.assertFalse(store.loaded)
        self.assertEqual(store.get("db.port", 1), 1)

    def test_snapshot_is_a_deep_copy(self):
        store = ConfigStore(Source(doc()), SCHEMA)
        store.load()
        snap = store.snapshot()
        snap["db"]["port"] = 1
        self.assertEqual(store.get("db.port"), 5432)

    def test_invalid_json_raises(self):
        store = ConfigStore(Source("{oops"), SCHEMA)
        with self.assertRaises(ConfigError):
            store.load()
        self.assertFalse(store.loaded)

    def test_schema_problems_are_reported(self):
        store = ConfigStore(Source(doc(port="5432")), SCHEMA)
        with self.assertRaises(ConfigError) as ctx:
            store.load()
        self.assertTrue(any("db.port" in p for p in ctx.exception.problems))

    def test_load_rereads_the_source(self):
        source = Source(doc())
        store = ConfigStore(source, SCHEMA)
        store.load()
        source.text = doc(port=6000)
        store.load()
        self.assertEqual(store.get("db.port"), 6000)


if __name__ == "__main__":
    unittest.main()
