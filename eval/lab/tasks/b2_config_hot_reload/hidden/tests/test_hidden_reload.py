import json
import unittest

from livecfg import ConfigError, ConfigStore, Field

SCHEMA = {
    "db.host": Field(str),
    "db.port": Field(int),
    "debug": Field(bool, required=False),
}

BASE = {
    "db": {"host": "db-1", "port": 5432, "pool": {"size": 5, "timeout": 1.5}},
    "dbx": {"host": "replica"},
    "debug": False,
    "tags": ["api", "eu"],
    "limits": 10,
}


def base():
    return json.loads(json.dumps(BASE))


class Source:
    def __init__(self, doc):
        self.set(doc)

    def set(self, doc):
        self.text = doc if isinstance(doc, str) else json.dumps(doc)

    def __call__(self):
        return self.text


class ReloadTestCase(unittest.TestCase):
    def setUp(self):
        self.source = Source(BASE)
        self.store = ConfigStore(self.source, SCHEMA)
        self.store.load()
        self.calls = []

    def record(self, prefix):
        return self.store.subscribe(prefix, lambda key, old, new: self.calls.append((key, old, new)))

    def reload_with(self, doc):
        self.source.set(doc)
        return self.store.reload()


class ReloadTests(ReloadTestCase):
    def test_returns_sorted_changed_leaf_keys(self):
        doc = base()
        doc["db"]["port"] = 5433
        doc["feature"] = {"beta": True}
        del doc["tags"]
        self.assertEqual(self.reload_with(doc), ["db.port", "feature.beta", "tags"])
        self.assertEqual(self.store.get("db.port"), 5433)
        self.assertIs(self.store.get("feature.beta"), True)
        self.assertIsNone(self.store.get("tags"))

    def test_unchanged_source_reports_nothing(self):
        self.record("")
        self.assertEqual(self.store.reload(), [])
        self.assertEqual(self.calls, [])

    def test_snapshot_reflects_new_config(self):
        doc = base()
        doc["db"]["host"] = "db-2"
        self.reload_with(doc)
        self.assertEqual(self.store.snapshot(), doc)

    def test_reload_before_load_diffs_against_empty(self):
        store = ConfigStore(Source(BASE), SCHEMA)
        calls = []
        store.subscribe("db", lambda key, old, new: calls.append((key, old, new)))
        changed = store.reload()
        self.assertEqual(
            changed,
            ["db.host", "db.pool.size", "db.pool.timeout", "db.port", "dbx.host", "debug", "limits", "tags"],
        )
        self.assertEqual(store.get("db.port"), 5432)
        self.assertEqual(
            calls,
            [
                ("db.host", None, "db-1"),
                ("db.pool.size", None, 5),
                ("db.pool.timeout", None, 1.5),
                ("db.port", None, 5432),
            ],
        )


class ChangeDetectionTests(ReloadTestCase):
    def test_callback_arguments_for_changed_added_and_removed(self):
        self.record("")
        doc = base()
        doc["db"]["port"] = 5433
        doc["feature"] = {"beta": True}
        del doc["tags"]
        self.reload_with(doc)
        self.assertEqual(
            self.calls,
            [("db.port", 5432, 5433), ("feature.beta", None, True), ("tags", ["api", "eu"], None)],
        )

    def test_lists_are_compared_as_leaves(self):
        self.record("tags")
        doc = base()
        doc["tags"] = ["api", "eu", "us"]
        self.assertEqual(self.reload_with(doc), ["tags"])
        self.assertEqual(self.calls, [("tags", ["api", "eu"], ["api", "eu", "us"])])

    def test_leaf_becoming_object_is_removal_plus_additions(self):
        self.record("limits")
        doc = base()
        doc["limits"] = {"rps": 10, "burst": 20}
        self.assertEqual(self.reload_with(doc), ["limits", "limits.burst", "limits.rps"])
        self.assertEqual(
            self.calls,
            [("limits", 10, None), ("limits.burst", None, 20), ("limits.rps", None, 10)],
        )

    def test_object_becoming_leaf(self):
        doc = base()
        doc["limits"] = {"rps": 10}
        self.reload_with(doc)
        self.record("")
        self.assertEqual(self.reload_with(base()), ["limits", "limits.rps"])
        self.assertEqual(self.calls, [("limits", None, 10), ("limits.rps", 10, None)])

    def test_notifications_arrive_in_sorted_key_order(self):
        self.record("")
        doc = base()
        doc["tags"] = []
        doc["debug"] = True
        doc["db"]["pool"]["size"] = 9
        doc["db"]["host"] = "db-9"
        self.reload_with(doc)
        self.assertEqual([c[0] for c in self.calls], ["db.host", "db.pool.size", "debug", "tags"])

    def test_callbacks_see_new_config(self):
        seen = []
        self.store.subscribe("db", lambda key, old, new: seen.append(self.store.get(key)))
        doc = base()
        doc["db"]["port"] = 6000
        self.reload_with(doc)
        self.assertEqual(seen, [6000])


class SubscriptionTests(ReloadTestCase):
    def test_prefix_matches_whole_segments(self):
        db, dbx = [], []
        self.store.subscribe("db", lambda *args: db.append(args))
        self.store.subscribe("dbx", lambda *args: dbx.append(args))
        doc = base()
        doc["db"]["host"] = "db-2"
        doc["dbx"]["host"] = "replica-2"
        self.reload_with(doc)
        self.assertEqual(db, [("db.host", "db-1", "db-2")])
        self.assertEqual(dbx, [("dbx.host", "replica", "replica-2")])

    def test_prefix_can_name_a_leaf(self):
        self.record("debug")
        self.record("db.port")
        doc = base()
        doc["debug"] = True
        doc["db"]["port"] = 5433
        doc["db"]["host"] = "db-2"
        self.reload_with(doc)
        self.assertCountEqual(self.calls, [("debug", False, True), ("db.port", 5432, 5433)])

    def test_nested_prefix(self):
        self.record("db.pool")
        doc = base()
        doc["db"]["pool"]["size"] = 10
        doc["db"]["port"] = 5433
        self.reload_with(doc)
        self.assertEqual(self.calls, [("db.pool.size", 5, 10)])

    def test_empty_prefix_sees_everything_and_each_subscriber_is_called(self):
        everything, pool, dbx = [], [], []
        self.store.subscribe("", lambda *a: everything.append(a[0]))
        self.store.subscribe("db.pool", lambda *a: pool.append(a[0]))
        self.store.subscribe("dbx", lambda *a: dbx.append(a[0]))
        doc = base()
        doc["db"]["pool"]["timeout"] = 3.0
        doc["limits"] = 20
        self.reload_with(doc)
        self.assertEqual(everything, ["db.pool.timeout", "limits"])
        self.assertEqual(pool, ["db.pool.timeout"])
        self.assertEqual(dbx, [])

    def test_unsubscribe_stops_notifications_and_is_safe_twice(self):
        unsubscribe = self.record("db")
        others = []
        self.store.subscribe("db", lambda *a: others.append(a[0]))
        unsubscribe()
        unsubscribe()
        doc = base()
        doc["db"]["port"] = 5433
        self.reload_with(doc)
        self.assertEqual(self.calls, [])
        self.assertEqual(others, ["db.port"])


class FailedReloadTests(ReloadTestCase):
    def setUp(self):
        super().setUp()
        self.record("")

    def assertUntouched(self):
        self.assertEqual(self.store.snapshot(), BASE)
        self.assertEqual(self.store.get("db.port"), 5432)
        self.assertEqual(self.calls, [])

    def test_unparsable_source_keeps_old_config(self):
        self.source.set("{not json")
        with self.assertRaises(ConfigError):
            self.store.reload()
        self.assertUntouched()

    def test_invalid_config_keeps_old_config(self):
        doc = base()
        doc["db"]["port"] = "5433"
        doc["limits"] = 99
        with self.assertRaises(ConfigError):
            self.reload_with(doc)
        self.assertUntouched()

    def test_missing_required_key_keeps_old_config(self):
        doc = base()
        del doc["db"]["host"]
        with self.assertRaises(ConfigError):
            self.reload_with(doc)
        self.assertUntouched()

    def test_next_good_reload_diffs_against_last_good_config(self):
        self.source.set("[]")
        with self.assertRaises(ConfigError):
            self.store.reload()
        doc = base()
        doc["limits"] = 11
        self.assertEqual(self.reload_with(doc), ["limits"])
        self.assertEqual(self.calls, [("limits", 10, 11)])


if __name__ == "__main__":
    unittest.main()
