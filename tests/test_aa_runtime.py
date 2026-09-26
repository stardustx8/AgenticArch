"""Runtime regression entry point; unchanged pre-HO02 cases live in runtime_legacy.

The legacy module is deliberately not a test_*.py file, so discovery runs each
case once. New behavioural tests remain here at the documented entry point.
"""
from runtime_legacy import *  # noqa: F403; retain the complete existing suite


class HO02ReviewTests(unittest.TestCase):
    def test_assertion_list_diff_and_suffix_are_not_discarded(self):
        from aa.context import focused_failure
        suffix = 'noise\n' * 800 + 'FAIL: test_values\nAssertionError: lists differ\n'
        suffix += '- [1, 2, 3]\n+ [1, 9, 3]\n' + 'details\n' * 15 + 'FAILED (failures=1)\n'
        text = 'prefix\n' * 500 + suffix
        result = focused_failure(text, 6000)
        self.assertEqual(result, text[-6000:])
        self.assertIn('+ [1, 9, 3]', focused_failure(result, 3000))

    def test_more_than_twelve_diagnostics_fit_and_unused_room_is_spent(self):
        from aa.context import focused_failure
        text = ''.join(f'noise {i}\n' * 25 + f'AssertionError: case-{i:02d}\n'
                       + f'- expected-{i}\n+ actual-{i}\n' for i in range(20)) + 'tail\n' * 50
        result = focused_failure(text, 5000)
        self.assertLessEqual(len(result), 5000)
        self.assertGreater(len(result), 4800)
        for i in range(20):
            self.assertIn(f'case-{i:02d}', result)
            self.assertIn(f'+ actual-{i}', result)

    def test_context_hard_cap_with_large_lines_and_tiny_budgets(self):
        from aa.context import focused_failure
        import random
        rng = random.Random(260927)
        for _ in range(250):
            text = ''.join(rng.choice(['noise', 'AssertionError:', '\n', 'x' * 100]) for _ in range(200))
            limit = rng.randrange(0, 2000)
            self.assertLessEqual(len(focused_failure(text, limit)), limit)


class HO02StopTests(unittest.TestCase):
    setUp = HarnessOptStopTests.setUp
    install = HarnessOptStopTests.install
    invoke = HarnessOptStopTests.invoke
    def test_subdirectory_runs_frozen_root_checks_but_symlink_escape_does_not(self):
        sub = self.wt / 'package'; sub.mkdir()
        settings = self.install({'test': 'test -f fixed'})
        reply, _ = self.invoke(settings, {'hook_event_name': 'Stop', 'cwd': str(sub)})
        self.assertEqual(reply['decision'], 'block')
        (self.wt / 'fixed').touch()
        self.assertEqual(self.invoke(settings, {'hook_event_name': 'Stop', 'cwd': str(sub)})[0], {})
        (self.wt / 'escape').symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.invoke(settings, {'hook_event_name': 'Stop', 'cwd': str(self.wt / 'escape')})[0], {})

    def test_capsule_and_project_settings_use_absolute_denies(self):
        settings = self.install()
        _, policy = self.invoke(settings)
        for path in (policy.parent, self.wt / '.claude'):
            self.assertNotIn(f'Write(/{path.as_posix()}/**)', settings['permissions']['deny'])
            self.assertIn(f'Edit(/{path.as_posix()}/**)', settings['permissions']['deny'])
        self.assertIs(settings['disableAllHooks'], False)

    def test_modified_hook_code_is_not_executed(self):
        settings = self.install()
        _, policy = self.invoke(settings)
        (policy.parent / 'hook.py').write_text("raise RuntimeError('foreign executable ran')")
        self.assertEqual(self.invoke(settings)[0], {})

