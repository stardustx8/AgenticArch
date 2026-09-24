import importlib.util
from pathlib import Path
import tempfile
import unittest

FILE = Path(__file__).resolve().parents[1] / 'tools/install_skills.py'
spec = importlib.util.spec_from_file_location('install_skills', FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.target = self.root / 'installed'
        for name in module.NAMES:
            path = self.source / name
            path.mkdir(parents=True)
            (path / 'SKILL.md').write_text('revised '+name)
        self.backups = self.root / 'backups'

    def test_dry_run_creates_nothing(self):
        report = module.install(self.source, self.target)
        self.assertEqual(report['mode'], 'DRY_RUN')
        self.assertEqual(len(report['changes']), 2)
        self.assertFalse(self.target.exists())

    def test_apply_preserves_helpers_and_backs_up_originals(self):
        path = self.target / module.NAMES[0]
        path.mkdir(parents=True)
        (path / 'SKILL.md').write_text('old')
        (path / 'helper.py').write_text('existing helper')
        report = module.install(self.source, self.target, apply=True, backup_root=self.backups)
        backup = Path(report['backup'])
        self.assertEqual((backup / module.NAMES[0] / 'SKILL.md').read_text(), 'old')
        self.assertEqual((path / 'helper.py').read_text(), 'existing helper')
        self.assertTrue((path / 'SKILL.md').read_text().startswith('revised'))
        self.assertEqual(backup.stat().st_mode & 0o777, 0o700)

    def test_apply_needs_backup(self):
        with self.assertRaises(ValueError):
            module.install(self.source, self.target, apply=True)
        self.assertFalse(self.target.exists())

    def test_no_op_is_idempotent(self):
        module.install(self.source, self.target, apply=True, backup_root=self.backups)
        report = module.install(self.source, self.target, apply=True, backup_root=self.backups)
        self.assertEqual(report['changes'], [])
        self.assertIsNone(report['backup'])

    def test_no_source_target_overlap(self):
        for target in (self.source, self.source / 'child', self.root):
            with self.subTest(target=target), self.assertRaises(ValueError):
                module.install(self.source, target)

    def test_no_discoverable_backup(self):
        with self.assertRaises(ValueError):
            module.install(self.source, self.target, apply=True, backup_root=self.target / 'backup')

    def test_rejects_existing_symlink(self):
        self.target.mkdir()
        (self.target / module.NAMES[0]).symlink_to(self.source / module.NAMES[0], target_is_directory=True)
        with self.assertRaises(ValueError):
            module.install(self.source, self.target)

    def test_rejects_source_symlink(self):
        (self.source / module.NAMES[0] / 'linked').symlink_to('/etc/hosts')
        with self.assertRaises(ValueError):
            module.install(self.source, self.target)


if __name__ == '__main__':
    unittest.main()
