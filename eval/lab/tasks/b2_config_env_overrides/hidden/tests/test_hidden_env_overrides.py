import os
import unittest
from unittest import mock

from appconfig import DEFAULTS, ConfigError, load_config


def load(env, text=None):
    return load_config(text, env=env)


class EnvOverrideTests(unittest.TestCase):
    def test_nested_int_override(self):
        cfg = load({"APP_DB__PORT": "5433"})
        self.assertEqual(cfg["db"]["port"], 5433)
        self.assertIsInstance(cfg["db"]["port"], int)
        self.assertEqual(cfg["db"]["host"], "localhost")

    def test_top_level_overrides(self):
        cfg = load({"APP_LOG_LEVEL": "debug", "APP_WORKERS": "16"})
        self.assertEqual(cfg["log_level"], "debug")
        self.assertEqual(cfg["workers"], 16)
        self.assertIsInstance(cfg["workers"], int)

    def test_float_override(self):
        self.assertEqual(load({"APP_DB__TIMEOUT": "0.5"})["db"]["timeout"], 0.5)
        timeout = load({"APP_DB__TIMEOUT": "3"})["db"]["timeout"]
        self.assertEqual(timeout, 3.0)
        self.assertIsInstance(timeout, float)

    def test_string_values_are_not_coerced(self):
        cfg = load({"APP_DB__HOST": "10.0.0.5", "APP_CACHE__BACKEND": "1"})
        self.assertEqual(cfg["db"]["host"], "10.0.0.5")
        self.assertEqual(cfg["cache"]["backend"], "1")

    def test_bool_spellings(self):
        cases = [
            ("true", True), ("TRUE", True), ("yes", True), ("Yes", True), ("1", True),
            ("false", False), ("False", False), ("no", False), ("NO", False), ("0", False),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                cfg = load({"APP_DB__SSL": raw, "APP_CACHE__ENABLED": raw})
                self.assertIs(cfg["db"]["ssl"], expected)
                self.assertIs(cfg["cache"]["enabled"], expected)

    def test_invalid_bool_raises_naming_variable(self):
        for raw in ("2", "maybe", "truthy"):
            with self.subTest(raw=raw):
                with self.assertRaises(ConfigError) as ctx:
                    load({"APP_CACHE__ENABLED": raw})
                self.assertIn("APP_CACHE__ENABLED", str(ctx.exception))

    def test_invalid_int_raises_naming_variable(self):
        for raw in ("5.5", "abc", ""):
            with self.subTest(raw=raw):
                with self.assertRaises(ConfigError) as ctx:
                    load({"APP_DB__PORT": raw})
                self.assertIn("APP_DB__PORT", str(ctx.exception))

    def test_invalid_float_raises_naming_variable(self):
        with self.assertRaises(ConfigError) as ctx:
            load({"APP_DB__TIMEOUT": "fast"})
        self.assertIn("APP_DB__TIMEOUT", str(ctx.exception))

    def test_unrelated_variables_ignored(self):
        env = {
            "DB__PORT": "1",
            "APPX_DB__PORT": "1",
            "MYAPP_WORKERS": "1",
            "APP_NOPE": "x",
            "APP_DB__NOPE": "x",
            "APP_CACHE": "off",
            "APP_LOG_LEVEL__DEEPER": "x",
            "PATH": "/usr/bin",
        }
        self.assertEqual(load(env), DEFAULTS)

    def test_keys_matched_case_insensitively(self):
        cfg = load({"APP_db__Port": "6543", "APP_Log_Level": "warning"})
        self.assertEqual(cfg["db"]["port"], 6543)
        self.assertEqual(cfg["log_level"], "warning")

    def test_env_wins_over_json_which_wins_over_defaults(self):
        text = '{"db": {"host": "db.internal", "port": 6000}, "cache": {"enabled": false}}'
        cfg = load({"APP_DB__PORT": "7000", "APP_CACHE__ENABLED": "yes"}, text=text)
        self.assertEqual(cfg["db"]["port"], 7000)
        self.assertEqual(cfg["db"]["host"], "db.internal")
        self.assertIs(cfg["cache"]["enabled"], True)
        self.assertEqual(cfg["cache"]["ttl"], 300)

    def test_defaults_not_mutated(self):
        load({"APP_DB__PORT": "1", "APP_CACHE__ENABLED": "no"})
        self.assertEqual(DEFAULTS["db"]["port"], 5432)
        self.assertIs(DEFAULTS["cache"]["enabled"], True)
        self.assertEqual(load({})["db"]["port"], 5432)

    def test_reads_os_environ_by_default(self):
        with mock.patch.dict(os.environ, {"APP_WORKERS": "12", "APP_DB__SSL": "true"}, clear=True):
            cfg = load_config()
        self.assertEqual(cfg["workers"], 12)
        self.assertIs(cfg["db"]["ssl"], True)

    def test_explicit_env_replaces_os_environ(self):
        with mock.patch.dict(os.environ, {"APP_WORKERS": "12"}, clear=True):
            cfg = load_config(env={"APP_DB__PORT": "5433"})
        self.assertEqual(cfg["workers"], 4)
        self.assertEqual(cfg["db"]["port"], 5433)


if __name__ == "__main__":
    unittest.main()
