import json
import os
import tempfile
import unittest

from appcfg import DEFAULTS, load, load_file


class HiddenFileLoadingRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, content):
        path = os.path.join(self.tmp.name, name)
        with open(path, 'w') as fh:
            fh.write(content)
        return path

    def test_missing_file_falls_back_to_defaults(self):
        missing = os.path.join(self.tmp.name, 'nope.json')
        self.assertEqual(load_file(missing), {})
        self.assertEqual(load(missing, environ={}), DEFAULTS)

    def test_malformed_json_falls_back_to_defaults(self):
        path = self.write('bad.json', '{not json')
        self.assertEqual(load_file(path), {})
        self.assertEqual(load(path, environ={}), DEFAULTS)

    def test_non_object_json_ignored(self):
        path = self.write('list.json', '[1, 2, 3]')
        self.assertEqual(load_file(path), {})
        self.assertEqual(load(path, environ={}), DEFAULTS)

    def test_extra_file_keys_are_kept(self):
        path = self.write('cfg.json', json.dumps({'workers': 3, 'feature_x': True}))
        cfg = load(path, environ={})
        self.assertIs(cfg['feature_x'], True)
        self.assertEqual(cfg['workers'], 3)
