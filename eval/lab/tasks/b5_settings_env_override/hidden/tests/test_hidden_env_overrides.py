import json
import os
import tempfile
import unittest
from unittest import mock

from appcfg import DEFAULTS, load


class HiddenEnvOverrideTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, content):
        path = os.path.join(self.tmp.name, name)
        with open(path, 'w') as fh:
            fh.write(content)
        return path

    def test_env_overrides_defaults_with_types(self):
        cfg = load(environ={'APP_WORKERS': '8', 'APP_DEBUG': 'TRUE', 'APP_LOG_LEVEL': 'debug'})
        self.assertEqual(cfg['workers'], 8)
        self.assertIs(cfg['debug'], True)
        self.assertEqual(cfg['log_level'], 'debug')
        self.assertEqual(cfg['bind'], '127.0.0.1:8000')

    def test_env_beats_file(self):
        path = self.write('cfg.json', json.dumps({'workers': 16, 'log_level': 'warning'}))
        cfg = load(path, environ={'APP_WORKERS': '2'})
        self.assertEqual(cfg['workers'], 2)
        self.assertEqual(cfg['log_level'], 'warning')

    def test_boolean_spellings(self):
        cases = [('1', True), ('0', False), ('true', True), ('False', False),
                 ('YES', True), ('no', False)]
        for raw, expected in cases:
            self.assertIs(load(environ={'APP_DEBUG': raw})['debug'], expected, raw)

    def test_bad_boolean_raises(self):
        with self.assertRaises(ValueError):
            load(environ={'APP_DEBUG': 'maybe'})

    def test_bad_int_raises(self):
        with self.assertRaises(ValueError):
            load(environ={'APP_WORKERS': 'lots'})

    def test_unknown_env_keys_ignored(self):
        cfg = load(environ={'APP_COLOR': 'blue', 'HOME': '/root', 'WORKERS': '9'})
        self.assertEqual(cfg, DEFAULTS)

    def test_uses_os_environ_by_default(self):
        with mock.patch.dict(os.environ, {'APP_WORKERS': '3'}):
            self.assertEqual(load()['workers'], 3)

    def test_defaults_not_mutated(self):
        load(environ={'APP_WORKERS': '8'})
        self.assertEqual(DEFAULTS['workers'], 4)
