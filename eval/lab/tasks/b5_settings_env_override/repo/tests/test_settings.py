import json
import os
import tempfile
import unittest

from appcfg import DEFAULTS, load


class LoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, content):
        path = os.path.join(self.tmp.name, name)
        with open(path, 'w') as fh:
            fh.write(content)
        return path

    def test_defaults(self):
        self.assertEqual(load(), DEFAULTS)

    def test_file_overrides_defaults(self):
        path = self.write('cfg.json', json.dumps({'workers': 16, 'debug': True}))
        cfg = load(path)
        self.assertEqual(cfg['workers'], 16)
        self.assertTrue(cfg['debug'])
        self.assertEqual(cfg['log_level'], 'info')

    def test_defaults_not_mutated(self):
        path = self.write('cfg.json', json.dumps({'workers': 2}))
        load(path)
        self.assertEqual(DEFAULTS['workers'], 4)


if __name__ == '__main__':
    unittest.main()
