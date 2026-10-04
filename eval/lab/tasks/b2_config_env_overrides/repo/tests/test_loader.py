import unittest

from appconfig import DEFAULTS, ConfigError, get, load_config


class LoadConfigTests(unittest.TestCase):
    def test_defaults_when_no_text(self):
        cfg = load_config()
        self.assertEqual(cfg["db"]["port"], 5432)
        self.assertIs(cfg["cache"]["enabled"], True)
        self.assertEqual(cfg["log_level"], "info")

    def test_json_is_deep_merged_over_defaults(self):
        cfg = load_config('{"db": {"host": "db.internal"}, "workers": 8}')
        self.assertEqual(cfg["db"]["host"], "db.internal")
        self.assertEqual(cfg["db"]["port"], 5432)
        self.assertEqual(cfg["workers"], 8)
        self.assertIs(cfg["cache"]["enabled"], True)

    def test_invalid_json_rejected(self):
        with self.assertRaises(ConfigError):
            load_config("{not json")

    def test_document_must_be_an_object(self):
        with self.assertRaises(ConfigError):
            load_config("[1, 2]")

    def test_unknown_keys_rejected(self):
        for text in ('{"dbx": {}}', '{"db": {"prt": 1}}'):
            with self.subTest(text=text):
                with self.assertRaises(ConfigError):
                    load_config(text)

    def test_section_must_stay_an_object(self):
        with self.assertRaises(ConfigError):
            load_config('{"db": 5}')

    def test_each_call_returns_a_fresh_copy(self):
        cfg = load_config()
        cfg["db"]["port"] = 1
        self.assertEqual(load_config()["db"]["port"], 5432)
        self.assertEqual(DEFAULTS["db"]["port"], 5432)


class GetTests(unittest.TestCase):
    def test_dotted_lookup(self):
        cfg = load_config()
        self.assertEqual(get(cfg, "db.port"), 5432)
        self.assertEqual(get(cfg, "db.nope", "x"), "x")
        self.assertIsNone(get(cfg, "log_level.deeper"))


if __name__ == "__main__":
    unittest.main()
