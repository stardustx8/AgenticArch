"""End-to-end tests of the aa runtime with fake model workers and real git repos.

Remotes are local bare repositories; Pro's connector commits are simulated by a
separate clone that pushes to the case branch.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aa import config, git
from aa.daemon import App
from aa.db import DB
from aa.workers import LANES, Result, Workers


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def init_repo(path: Path, files: dict[str, str]) -> None:
    path.mkdir(parents=True)
    sh(path, 'git', 'init', '-q', '-b', 'main')
    sh(path, 'git', 'config', 'user.email', 't@t')
    sh(path, 'git', 'config', 'user.name', 't')
    for k, v in files.items():
        (path / k).parent.mkdir(parents=True, exist_ok=True)
        (path / k).write_text(v)
    sh(path, 'git', 'add', '-A')
    sh(path, 'git', 'commit', '-q', '-m', 'init')


class FakeCLM:
    def __init__(self, tier=None, peer=None, probs_conf=0.9):
        self.tier, self.peer, self.conf = tier, peer, probs_conf
        self.calls = []

    def _probs(self, pick, options):
        rest = (1 - self.conf) / (len(options) - 1)
        return {k: (self.conf if k == pick else rest) for k in options}

    def choose(self, kind, task_id, state, question, options):
        self.calls.append(kind)
        pick = self.tier if kind == 'tier' else self.peer
        if pick is None:
            return None, None, 0
        return pick, self._probs(pick, options), 0

    def rank(self, task_id, context, question, candidates, k):
        return candidates[:k]


class FakeWorkers(Workers):
    """Scripted behaviour per job kind; records every call."""

    def __init__(self, cfg, script):
        super().__init__(cfg, runner=None)
        self.script, self.calls = script, []

    def local_available(self):
        return bool(self.script.get('local'))

    def verify_billing(self, cli):
        if self.script.get('billing_error'):
            from aa.workers import BillingError
            raise BillingError('no subscription')

    def execute(self, lane, prompt, cwd, *, write=True, extra_dirs=(), schema=None, log_name='job'):
        self.verify_billing(lane.cli)
        self.calls.append((lane.name, log_name))
        if log_name.endswith('-triage'):
            if self.script['triage'] is None:
                return Result(False, '', None, [], error='triage timeout')
            return Result(True, '', self.script['triage'], [lane.model])
        kind = _kind(log_name)
        if kind == 'spec' and 'spec' not in self.script:
            return Result(True, '', spec_verdict([]), [lane.model])      # default: all criteria met
        if kind == 'pick' and 'pick' not in self.script:
            return Result(True, '', {'winner': 'A', 'reason': 'default'}, [lane.model])
        fn = self.script[kind]
        return fn(lane, Path(cwd), prompt, extra_dirs)


def spec_verdict(unmet: list[str], tampering: bool = False) -> dict:
    """Verdict for the single test criterion 'a'; unmet names become the judged criterion text."""
    if unmet:
        crit = [{'index': 1, 'criterion': ', '.join(unmet), 'met': False, 'reason': f'{", ".join(unmet)} missing'}]
    else:
        crit = [{'index': 1, 'criterion': 'a', 'met': True, 'reason': 'ok'}]
    return {'criteria': crit, 'tampering': tampering, 'tampering_reason': 'skipped a test' if tampering else ''}


def _kind(log_name: str) -> str:
    if log_name.endswith('-spec'):
        return 'spec'
    if log_name.endswith('-oracle'):
        return 'oracle'
    if '-pick-' in log_name:
        return 'pick'
    if '-race-' in log_name:
        return 'work'
    for k in ('-fix', '-opus', '-astra'):
        if k in log_name:
            return k.strip('-')
    return 'work'


def triage(tier, cats=(), peer='astra', testable=False):
    return {'tier': tier, 'peer': peer, 'pro_categories': list(cats), 'summary': 's',
            'acceptance_criteria': ['a'], 'relevant_paths': ['app.py'], 'risks': [], 'owner_question': '',
            'testable': testable}


def oracle_writer(body='test -f done.txt\n', command='sh tests/check_feature.sh'):
    def fn(lane, cwd, prompt, extra):
        (cwd / 'tests').mkdir(exist_ok=True)
        (cwd / 'tests' / 'check_feature.sh').write_text(body)
        (cwd / 'app.py').write_text('print("oracle must not touch production code")\n')
        return Result(True, '{}', {'test_files': ['tests/check_feature.sh'], 'command': command, 'notes': ''},
                      [lane.model])
    return fn


class Env:
    def __init__(self, tmp: Path, script: dict, clm: FakeCLM, checks='test -f done.txt', policy='codex',
                 triage=True, oracle=False, best_of_2=False, local=False):
        self.tmp = tmp
        # Target repo with a bare origin.
        self.target_origin = tmp / 'target.git'
        sh(tmp, 'git', 'init', '-q', '--bare', '-b', 'main', str(self.target_origin))
        self.target = tmp / 'target'
        init_repo(self.target, {'app.py': 'print(1)\n',
                                '.agenticarch.toml': f'[checks]\ntest = "{checks}"\n'})
        sh(self.target, 'git', 'remote', 'add', 'origin', str(self.target_origin))
        sh(self.target, 'git', 'push', '-q', 'origin', 'main')
        # Empty case repo remote.
        self.case_origin = tmp / 'cases.git'
        sh(tmp, 'git', 'init', '-q', '--bare', '-b', 'main', str(self.case_origin))
        self.cfg = config.load(Path('/nonexistent'), {
            'paths': {'state_dir': str(tmp / 'state')},
            'case_repo': {'url': str(self.case_origin), 'slug': 'me/cases'},
            'ntfy': {'enabled': False},
            'delivery': {'push_branch': True},
            'triage': {'policy': policy},
            'failure_triage': {'enabled': triage},
            'oracle_tests': {'enabled': oracle},
            'best_of_2': {'enabled': best_of_2},
            'local_llm': {'enabled': local, 'url': 'http://127.0.0.1:9'},   # never a real server
        })
        self.db = DB(':memory:')
        self.clock = 1e9
        self.sent = []
        self.workers = FakeWorkers(self.cfg, script)
        self.app = App(self.cfg, self.db, self.workers, clm)
        self.app.n.send = lambda title, msg, **kw: self.sent.append((title, msg, kw))
        self.slug_patch = mock.patch('aa.git.github_slug', return_value='me/target')
        self.slug_patch.start()

    def close(self):
        self.slug_patch.stop()

    def run(self, n=40):
        idle = 0
        for _ in range(n):
            self.clock += 1000          # every tick is 'later' so Pro polls are not throttled
            if self.app.tick(now=self.clock):
                idle = 0
            else:
                idle += 1
                if idle >= 2:
                    break

    def pro_commit(self, case_id, files: dict[str, str], msg='pro'):
        """Simulate GPT-6 Pro writing to the case branch through the connector."""
        clone = self.tmp / f'pro-{case_id}'
        if not clone.exists():
            sh(self.tmp, 'git', 'clone', '-q', str(self.case_origin), str(clone))
            sh(clone, 'git', 'config', 'user.email', 'pro@x')
            sh(clone, 'git', 'config', 'user.name', 'pro')
        sh(clone, 'git', 'fetch', '-q', 'origin')
        sh(clone, 'git', 'checkout', '-q', '-B', f'case/{case_id}', f'origin/case/{case_id}')
        for k, v in files.items():
            p = clone / k
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(v)
        sh(clone, 'git', 'add', '-A')
        sh(clone, 'git', 'commit', '-q', '-m', msg)
        sh(clone, 'git', 'push', '-q', 'origin', f'case/{case_id}')

    def pro_implement(self, branch, base, files):
        clone = self.tmp / 'pro-target'
        if not clone.exists():
            sh(self.tmp, 'git', 'clone', '-q', str(self.target_origin), str(clone))
            sh(clone, 'git', 'config', 'user.email', 'pro@x')
            sh(clone, 'git', 'config', 'user.name', 'pro')
        sh(clone, 'git', 'fetch', '-q', 'origin')
        sh(clone, 'git', 'checkout', '-q', '-B', branch, base)
        for k, v in files.items():
            (clone / k).write_text(v)
        sh(clone, 'git', 'add', '-A')
        sh(clone, 'git', 'commit', '-q', '-m', 'impl')
        sh(clone, 'git', 'push', '-q', 'origin', branch)
        return sh(clone, 'git', 'rev-parse', 'HEAD')


def write_done(lane, cwd, prompt, extra):
    (cwd / 'done.txt').write_text('ok')
    (cwd / '__pycache__').mkdir(exist_ok=True)          # worker ran tests itself
    (cwd / '__pycache__' / 'app.cpython-314.pyc').write_bytes(b'x')
    return Result(True, 'implemented', None, [lane.model])


def noop(lane, cwd, prompt, extra):
    return Result(True, 'nothing', None, [lane.model])


def challenger(verdict, touch_outside=False):
    def fn(lane, cwd, prompt, extra):
        turn = next(l.split('turns/')[1].split()[0] for l in prompt.splitlines() if 'turns/' in l and 'write' in l)
        case_dir = Path(next(l.split(': ', 1)[1] for l in prompt.splitlines() if l.startswith('Case directory')).split(' (')[0])
        (case_dir / 'SOLUTION.md').write_text((case_dir / 'SOLUTION.md').read_text() + f'\n{lane.name} edit\n')
        (case_dir / 'turns' / turn).write_text(f'checked\nVERDICT: {verdict}\n')
        if touch_outside:
            (cwd / 'README.md').write_text('hacked')
            (extra[0] / 'app.py').write_text('hacked')
        return Result(True, 'done', None, [lane.model])
    return fn


class LocalFlowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self.env.close()
        self._tmp.cleanup()

    def test_routine_task_agreeing_votes_runs_luna_low_and_delivers_branch(self):
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done}, FakeCLM('routine'),
                       checks='test -f done.txt && touch artefact.cache')
        tid = self.env.app.tasks.create(self.env.target, 'rename a thing')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE', t)
        self.assertEqual((t['tier'], t['tier_source'], t['lane']), ('routine', 'agree', 'luna_low'))
        self.assertIn(f'aa/{tid}', sh(self.env.target_origin, 'git', 'branch', '--list'))
        self.assertEqual(sh(self.env.target, 'git', 'show', f'aa/{tid}:done.txt'), 'ok')
        self.assertFalse((self.env.cfg.worktrees / tid).exists())
        # One squashed commit on top of the base; no check artefacts committed.
        base = self.env.db.task(tid)['base_ref']
        self.assertEqual(sh(self.env.target, 'git', 'rev-list', '--count', f'{base}..aa/{tid}'), '1')
        self.assertEqual(sh(self.env.target, 'git', 'diff', '--name-only', f'{base}..aa/{tid}'), 'done.txt')

    def test_codex_policy_uses_codex_tier_and_logs_decider_vote(self):
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': write_done}, FakeCLM('tough'))
        tid = self.env.app.tasks.create(self.env.target, 'fix bug')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['tier'], t['tier_source']), ('DONE', 'bounded', 'codex'))
        self.assertEqual(t['data']['tier_votes']['decider'], 'tough')     # shadow vote kept

    def test_decider_is_fallback_when_codex_triage_fails(self):
        self.env = Env(self.tmp, {'triage': None, 'work': write_done}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['tier'], t['tier_source']), ('DONE', 'routine', 'decider'))

    def test_higher_if_1_takes_higher_vote_and_asks_on_big_gap(self):
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': write_done}, FakeCLM('medium_tough'),
                       policy='higher_if_1')
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['tier'], 'medium_tough')
        self.env.app.tasks.decider = FakeCLM('tough')
        tid2 = self.env.app.tasks.create(self.env.target, 'y')
        self.env.run()
        self.assertEqual(self.env.db.task(tid2)['status'], 'WAIT_OWNER')

    def test_codex_policy_uses_codex_peer(self):
        self.env = Env(self.tmp, {'triage': triage('medium_tough', peer='opus'), 'work': write_done},
                       FakeCLM('medium_tough', peer='astra'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['lane'], 'opus_high')

    def test_disagreement_asks_owner_then_uses_pick(self):
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': write_done}, FakeCLM('tough'),
                       policy='ask_on_disagreement')
        tid = self.env.app.tasks.create(self.env.target, 'fix bug')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'WAIT_OWNER')
        title, msg, kw = self.env.sent[-1]
        self.assertIn('Tier?', title)
        self.assertIn(('bounded', f'tier {tid} bounded'), kw['choices'])
        self.env.db.inbox_put(f'tier {tid} bounded')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['tier_source'], t['lane']), ('DONE', 'owner_pick', 'luna_high'))

    def test_low_confidence_clm_is_an_abstention(self):
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': write_done},
                       FakeCLM('tough', probs_conf=0.3), policy='ask_on_disagreement')
        tid = self.env.app.tasks.create(self.env.target, 'fix bug')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['tier_source']), ('DONE', 'codex'))

    def test_failed_checks_retry_then_escalate_lane(self):
        attempts = []

        def flaky(lane, cwd, prompt, extra):
            attempts.append((lane.name, 'Feedback on it' in prompt and 'exit' in prompt))
            if len(attempts) == 3:
                (cwd / 'done.txt').write_text('ok')
            return Result(True, 'tried', None, [lane.model])

        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': flaky}, FakeCLM('routine'), triage=False)
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        self.assertEqual([a[0] for a in attempts], ['luna_low', 'luna_low', 'luna_high'])
        self.assertTrue(attempts[1][1], 'retry prompt must include the failing checks')

    def test_medium_tough_uses_decider_peer_choice(self):
        self.env = Env(self.tmp, {'triage': triage('medium_tough'), 'work': write_done},
                       FakeCLM('medium_tough', peer='opus'), policy='ask_on_disagreement')
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['lane'], 'opus_high')

    def test_medium_peer_escalates_to_other_model_then_deep(self):
        fail = lambda lane, cwd, prompt, extra: Result(True, 'tried', None, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('medium_tough'), 'work': fail},
                       FakeCLM('medium_tough', peer='astra'), triage=False)
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(60)
        t = self.env.db.task(tid)
        lanes = [c[0] for c in self.env.workers.calls if not c[1].endswith('-triage')]
        self.assertEqual(lanes[:4], ['astra_high', 'astra_high', 'opus_high', 'opus_high'])
        self.assertNotIn('opus_medium', lanes, 'peer choice switches models only, not effort')
        self.assertEqual(t['status'], 'DEEP')

    def test_spec_loop_sends_back_until_criteria_met(self):
        verdicts = [spec_verdict(['handles empty input']), spec_verdict([])]
        prompts = []

        def judge(lane, cwd, prompt, extra):
            prompts.append(prompt)
            return Result(True, '', verdicts.pop(0), [lane.model])

        def work(lane, cwd, prompt, extra):
            prompts.append(prompt)
            (cwd / 'done.txt').write_text('ok' + str(len(prompts)))
            return Result(True, 'REBUTTAL: empty input handled in app.py:3' if len(prompts) > 2 else 'done',
                          None, [lane.model])

        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': work, 'spec': judge}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertEqual(t['data']['spec_loops'], 1)
        self.assertIn('UNMET: handles empty input', prompts[2])          # worker saw the finding
        self.assertIn('REBUTTAL: empty input handled', prompts[3])      # judge saw the rebuttal
        spec_lane = [c[0] for c in self.env.workers.calls if c[1].endswith('-spec')]
        self.assertEqual(spec_lane, ['opus_medium', 'opus_medium'])
        self.assertEqual(t['passes'], 1, 'spec loops do not consume the check-retry budget')

    def test_spec_loop_stops_after_max_loops_and_owner_accepts(self):
        judge = lambda lane, cwd, prompt, extra: Result(True, '', spec_verdict(['criterion b']), [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done, 'spec': judge},
                       FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(80)
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['data']['spec_loops']), ('WAIT_OWNER', 3))
        self.assertEqual(len([c for c in self.env.workers.calls if c[1].endswith('-spec')]), 4)
        title, msg, kw = self.env.sent[-1]
        self.assertIn('Spec not met', title)
        self.assertIn(('Accept', f'accept {tid}'), kw['choices'])
        self.env.db.inbox_put(f'accept {tid}')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        msg = sh(self.env.target, 'git', 'log', '-1', '--format=%B', f'aa/{tid}')
        self.assertIn('accepted by owner', msg)

    def test_owner_one_more_spec_loop(self):
        verdicts = [spec_verdict(['b'])] * 4 + [spec_verdict([])]
        judge = lambda lane, cwd, prompt, extra: Result(True, '', verdicts.pop(0), [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done, 'spec': judge},
                       FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(80)
        self.assertEqual(self.env.db.task(tid)['status'], 'WAIT_OWNER')
        self.env.db.inbox_put(f'retry {tid}')
        self.env.run(40)
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['data']['spec_loops']), ('DONE', 4))

    def test_tampering_flag_sends_back(self):
        verdicts = [spec_verdict([], tampering=True), spec_verdict([])]
        judge = lambda lane, cwd, prompt, extra: Result(True, '', verdicts.pop(0), [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done, 'spec': judge},
                       FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['data']['spec_loops']), ('DONE', 1))
        self.assertTrue(t['data']['spec_reviews'][0]['tampering'])

    def test_no_acceptance_criteria_judges_task_statement(self):
        prompts = []

        def judge(lane, cwd, prompt, extra):
            prompts.append(prompt)
            return Result(True, '', spec_verdict([]), [lane.model])
        tri = triage('routine')
        tri['acceptance_criteria'] = []
        self.env = Env(self.tmp, {'triage': tri, 'work': write_done, 'spec': judge}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'add the widget')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        self.assertIn('fully implemented exactly as stated', prompts[0])

    def test_spec_judge_failure_blocks_after_retries(self):
        bad = lambda lane, cwd, prompt, extra: Result(False, '', None, [], error='timeout')
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done, 'spec': bad},
                       FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(40)
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'BLOCKED')
        self.assertIn('spec judge failed', t['result'])

    def test_worker_auth_failure_blocks_without_escalation(self):
        from aa.workers import BillingError

        def rejected(lane, cwd, prompt, extra):
            raise BillingError('Codex login rejected by the server (401)')
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': rejected}, FakeCLM('bounded'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['lane']), ('BLOCKED', 'luna_high'))
        self.assertIn('login rejected', t['result'])

    def test_environment_failure_pauses_then_retry_after_fix(self):
        env_file = self.tmp / 'db-up'
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done}, FakeCLM('routine', peer='environment'),
                       checks=f'test -f {env_file} || {{ echo connection refused; exit 1; }}')
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'WAIT_OWNER')
        self.assertTrue(t['data']['env_wait'])
        self.assertIn('Environment problem', self.env.sent[-1][0])
        self.assertEqual(len([c for c in self.env.workers.calls if not c[1].endswith(('-triage', '-spec'))]), 1,
                         'no worker retry on an environment failure')
        env_file.write_text('up')
        self.env.db.inbox_put(f'retry {tid}')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')

    def test_environment_can_be_treated_as_code(self):
        works = []

        def work(lane, cwd, prompt, extra):
            works.append(prompt)
            return Result(True, 'done', None, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': work}, FakeCLM('routine', peer='environment'),
                       checks='echo connection refused; exit 1')
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        self.env.db.inbox_put(f'code {tid}')
        self.env.run(3)
        self.assertEqual(len(works), 2)
        self.assertIn('connection refused', works[1])

    def test_flaky_check_passes_without_worker_retry(self):
        flag = self.tmp / 'flaky-once'
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done}, FakeCLM('routine', peer='code'),
                       checks=f'test -f {flag} || {{ touch {flag}; exit 1; }}')
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['passes']), ('DONE', 1))
        msg = sh(self.env.target, 'git', 'log', '-1', '--format=%B', f'aa/{tid}')
        self.assertIn('was flaky', msg)

    def test_pre_existing_failure_goes_to_judge_with_note(self):
        prompts = []

        def judge(lane, cwd, prompt, extra):
            prompts.append(prompt)
            return Result(True, '', spec_verdict([]), [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done, 'spec': judge},
                       FakeCLM('routine', peer='code'), checks="echo 'Error: legacy broken'; exit 1")
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertIn('base commit before the change: test', prompts[0])
        self.assertFalse((self.env.cfg.state_dir / 'base-wt' / tid).exists(), 'base worktree cleaned up')

    def test_incomplete_spec_verdict_never_passes(self):
        empty = lambda lane, cwd, prompt, extra: Result(True, '', {'criteria': [], 'tampering': False,
                                                                   'tampering_reason': ''}, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done, 'spec': empty},
                       FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(40)
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'BLOCKED')
        self.assertIn('judged criteria []', t['result'])

    def test_billing_error_blocks_without_dispatch(self):
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done, 'billing_error': True},
                       FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x', tier='routine')
        self.env.db.update_task(tid, status='TRIAGED')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'BLOCKED')
        self.assertIn('billing', t['result'])
        self.assertEqual(self.env.workers.calls, [])

    def test_autodetected_checks_need_owner_confirmation_once(self):
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done}, FakeCLM('routine'))
        sh(self.env.target, 'git', 'rm', '-q', '.agenticarch.toml')
        (self.env.target / 'Makefile').write_text('test:\n\ttest -f done.txt\n')
        sh(self.env.target, 'git', 'add', '-A')
        sh(self.env.target, 'git', 'commit', '-q', '-m', 'make')
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'WAIT_OWNER')
        self.assertIn('make test', self.env.sent[-1][1])
        self.env.db.inbox_put(f'checks {tid} ok')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        tid2 = self.env.app.tasks.create(self.env.target, 'y')
        self.env.run()
        self.assertEqual(self.env.db.task(tid2)['status'], 'DONE')

    def test_worker_blocked_line_pauses_task(self):
        blocked = lambda lane, cwd, prompt, extra: Result(True, 'BLOCKED: need API docs', None, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': blocked}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'WAIT_OWNER')                   # legacy text marker still understood
        self.assertEqual(t['data']['worker_question'], 'need API docs')

    def test_structured_blocked_question_then_owner_answer(self):
        prompts = []

        def work(lane, cwd, prompt, extra):
            prompts.append(prompt)
            if len(prompts) == 1:
                return Result(True, '{}', {'status': 'blocked', 'summary': 'stopped', 'open_items': [],
                                           'question': 'CSV or JSON export?', 'rebuttals': []}, [lane.model])
            (cwd / 'done.txt').write_text('ok')
            return Result(True, '{}', {'status': 'done', 'summary': 'did CSV', 'open_items': [],
                                       'question': '', 'rebuttals': []}, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': work}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'export')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'WAIT_OWNER')
        title, msg, kw = self.env.sent[-1]
        self.assertIn('Question from worker', title)
        self.assertIn('CSV or JSON export?', msg)
        self.env.db.inbox_put(f'answer {tid} CSV please')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['passes']), ('DONE', 1), 'owner answers do not consume retries')
        self.assertIn('A: CSV please', prompts[1])

    def test_triage_owner_question_asked_before_dispatch(self):
        triage_prompts = []
        first = dict(triage('tough', ['research']), owner_question='Which exchange rate should be used?')
        second = triage('routine')

        class W(FakeWorkers):
            def execute(s, lane, prompt, cwd, **kw):
                if kw.get('log_name', '').endswith('-triage'):
                    triage_prompts.append(prompt)
                    s.calls.append((lane.name, kw['log_name']))
                    return Result(True, '', first if len(triage_prompts) == 1 else second, [lane.model])
                return super().execute(lane, prompt, cwd, **kw)
        self.env = Env(self.tmp, {'triage': None, 'work': write_done}, FakeCLM('routine'))
        self.env.app.tasks.workers = W(self.env.cfg, {'work': write_done})
        tid = self.env.app.tasks.create(self.env.target, 'convert usd')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['case_id']), ('WAIT_OWNER', None), 'asked, not routed to Pro')
        self.assertIn('Which exchange rate', self.env.sent[-1][1])
        self.env.db.inbox_put(f'answer {tid} 0.92 EUR per USD, fixed')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['tier']), ('DONE', 'routine'))
        self.assertIn('A: 0.92 EUR per USD', triage_prompts[1])

    def test_partial_status_goes_back_without_running_checks(self):
        prompts = []

        def work(lane, cwd, prompt, extra):
            prompts.append(prompt)
            if len(prompts) == 1:
                return Result(True, '{}', {'status': 'partial', 'summary': 'backend only', 'open_items': ['UI part'],
                                           'question': '', 'rebuttals': []}, [lane.model])
            (cwd / 'done.txt').write_text('ok')
            return Result(True, '{}', {'status': 'done', 'summary': 'all', 'open_items': [], 'question': '',
                                       'rebuttals': []}, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': work}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertIn('Still required:\n- UI part', prompts[1])
        kinds = [r['kind'] for r in self.env.db.q('SELECT kind FROM events WHERE task_id=?', (tid,))]
        self.assertIn('worker_partial', kinds)
        self.assertNotIn('failure_triage', kinds, 'checks were not run on known-partial work')

    def test_rebuttals_field_reaches_spec_judge(self):
        judged = []
        verdicts = [spec_verdict(['b']), spec_verdict([])]

        def judge(lane, cwd, prompt, extra):
            judged.append(prompt)
            return Result(True, '', verdicts.pop(0), [lane.model])

        def work(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text('ok')
            reb = ['b is satisfied in app.py:1'] if 'reviewer' in prompt else []
            return Result(True, '{}', {'status': 'done', 'summary': 's', 'open_items': [], 'question': '',
                                       'rebuttals': reb}, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': work, 'spec': judge}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(60)
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        self.assertIn('b is satisfied in app.py:1', judged[1])

    def test_crash_recovery_clears_busy_flags(self):
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.db.x('UPDATE tasks SET busy=1')
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'NEW')
        self.env.app.recover()
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')


class DeepFlowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self.env.close()
        self._tmp.cleanup()

    def start(self, script):
        base = {'triage': triage('tough', ['architecture'])}
        base.update(script)
        self.env = Env(self.tmp, base, FakeCLM('tough'))
        tid = self.env.app.tasks.create(self.env.target, 'design the thing')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DEEP')
        return tid, t['case_id']

    def draft(self, cid):
        self.env.pro_commit(cid, {f'cases/{cid}/SOLUTION.md': '# Solution\n',
                                  f'cases/{cid}/OBJECTIONS.md': '| ID |\n',
                                  f'cases/{cid}/turns/pro-01.md': f'draft\nTURN-COMPLETE: {cid}/01\n'})

    def test_full_deep_flow_to_verified_implementation(self):
        tid, cid = self.start({'opus': challenger('AGREE'), 'astra': challenger('AGREE')})
        c = self.env.db.case(cid)
        self.assertEqual(c['phase'], 'WAIT_PRO')
        self.assertIn('PRO-TURN-01.md', c['data']['pro_prompt'])
        self.assertIn('NEW GPT-6 Pro chat', self.env.sent[-1][1])
        brief = sh(self.env.case_origin, 'git', 'show', f'case/{cid}:cases/{cid}/BRIEF.md')
        self.assertIn('design the thing', brief)
        self.assertIn(f'aa/base-{cid}', sh(self.env.target_origin, 'git', 'branch', '--list'))
        self.env.run()
        self.assertEqual(self.env.db.case(cid)['phase'], 'WAIT_PRO', 'no marker yet')
        self.draft(cid)
        self.env.run()
        c = self.env.db.case(cid)
        # Both agreed in round 1 -> straight to Pro review turn 02.
        self.assertEqual((c['phase'], c['pro_turn'], c['round']), ('WAIT_PRO', 2, 1))
        self.assertIn('SAME Pro chat', self.env.sent[-1][1])
        solution = sh(self.env.case_origin, 'git', 'show', f'case/{cid}:cases/{cid}/SOLUTION.md')
        self.assertIn('opus_high edit', solution)
        self.assertIn('astra_high edit', solution)
        base = self.env.db.task(tid)['base_ref']
        sha = self.env.pro_implement(f'aa/case-{cid}', base, {'done.txt': 'ok'})
        self.env.pro_commit(cid, {f'cases/{cid}/turns/pro-02.md':
                                  f'fine\nDECISION: GO\nTARGET-BRANCH: aa/case-{cid}\n'
                                  f'TARGET-COMMIT: {sha}\nTURN-COMPLETE: {cid}/02\n'})
        self.env.run()
        self.assertEqual(self.env.db.case(cid)['phase'], 'DONE')
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')

    def test_challengers_iterate_until_rounds_exhausted(self):
        tid, cid = self.start({'opus': challenger('REVISE'), 'astra': challenger('AGREE')})
        self.draft(cid)
        self.env.run(60)
        c = self.env.db.case(cid)
        self.assertEqual((c['phase'], c['pro_turn'], c['round']), ('WAIT_PRO', 2, 5))
        opus = [x for x in self.env.workers.calls if x[0] == 'opus_high']
        self.assertEqual(len(opus), 5)

    def test_scope_violations_are_reverted(self):
        tid, cid = self.start({'opus': challenger('AGREE', touch_outside=True),
                               'astra': challenger('AGREE')})
        self.draft(cid)
        self.env.run()
        files = sh(self.env.case_origin, 'git', 'ls-tree', '-r', '--name-only', f'case/{cid}')
        self.assertNotIn('hacked', sh(self.env.case_origin, 'git', 'show', f'case/{cid}:README.md'))
        self.assertTrue(all(f.startswith(f'cases/{cid}/') or f in ('README.md', 'PROTOCOL.md')
                            for f in files.splitlines()))
        ro = self.env.cfg.state_dir / 'target-ro' / cid / 'app.py'
        self.assertEqual(ro.read_text(), 'print(1)\n')
        kinds = [r['kind'] for r in self.env.db.q('SELECT kind FROM events')]
        self.assertIn('scope_violation', kinds)

    def test_clarify_with_owner_questions_then_answer_starts_next_cycle(self):
        tid, cid = self.start({'opus': challenger('AGREE'), 'astra': challenger('AGREE')})
        self.draft(cid)
        self.env.run()
        self.env.pro_commit(cid, {f'cases/{cid}/turns/pro-02.md':
                                  'DECISION: CLARIFY\n\n## Owner questions\n\nPostgres or SQLite?\n\n'
                                  f'TURN-COMPLETE: {cid}/02\n'})
        self.env.run()
        c = self.env.db.case(cid)
        self.assertEqual(c['phase'], 'WAIT_OWNER')
        self.assertIn('Postgres or SQLite?', self.env.sent[-1][1])
        self.env.db.inbox_put(f'answer {cid} Postgres, we already run it')
        self.env.run()
        c = self.env.db.case(cid)
        self.assertEqual((c['phase'], c['cycle'], c['pro_turn']), ('WAIT_PRO', 2, 3))
        ans = sh(self.env.case_origin, 'git', 'show', f'case/{cid}:cases/{cid}/OWNER-ANSWERS.md')
        self.assertIn('Postgres, we already run it', ans)
        turn3 = sh(self.env.case_origin, 'git', 'show', f'case/{cid}:cases/{cid}/PRO-TURN-03.md')
        self.assertIn('OWNER-ANSWERS.md', turn3)

    def test_pause_after_two_reviews_without_go_and_resume(self):
        tid, cid = self.start({'opus': challenger('AGREE'), 'astra': challenger('AGREE')})
        self.draft(cid)
        self.env.run()
        for nn in (2, 3):
            self.env.pro_commit(cid, {f'cases/{cid}/turns/pro-{nn:02d}.md':
                                      f'DECISION: CLARIFY\nTURN-COMPLETE: {cid}/{nn:02d}\n'})
            self.env.run()
        c = self.env.db.case(cid)
        self.assertEqual((c['phase'], c['pro_reviews']), ('PAUSED', 2))
        self.env.db.inbox_put(f'resume {cid}')
        self.env.run()
        self.assertEqual(self.env.db.case(cid)['phase'], 'WAIT_PRO')
        self.assertEqual(self.env.db.case(cid)['pro_turn'], 4)

    def test_post_go_failure_is_fixed_locally(self):
        def fix(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text('ok')
            return Result(True, 'fixed', None, [lane.model])
        tid, cid = self.start({'opus': challenger('AGREE'), 'astra': challenger('AGREE'), 'fix': fix})
        self.draft(cid)
        self.env.run()
        base = self.env.db.task(tid)['base_ref']
        sha = self.env.pro_implement(f'aa/case-{cid}', base, {'app.py': 'print(2)\n'})
        self.env.pro_commit(cid, {f'cases/{cid}/turns/pro-02.md':
                                  f'DECISION: GO\nTARGET-BRANCH: aa/case-{cid}\nTARGET-COMMIT: {sha}\n'
                                  f'TURN-COMPLETE: {cid}/02\n'})
        self.env.run()
        self.assertEqual(self.env.db.case(cid)['phase'], 'DONE')
        self.assertEqual(sh(self.env.target_origin, 'git', 'show', f'aa/case-{cid}:done.txt'), 'ok')

    def test_undeclared_commit_after_go_goes_back_to_pro(self):
        tid, cid = self.start({'opus': challenger('AGREE'), 'astra': challenger('AGREE')})
        self.draft(cid)
        self.env.run()
        base = self.env.db.task(tid)['base_ref']
        sha = self.env.pro_implement(f'aa/case-{cid}', base, {'done.txt': 'ok'})
        self.env.pro_implement(f'aa/case-{cid}', sha, {'extra.txt': 'undeclared'})   # tip moves on
        self.env.pro_commit(cid, {f'cases/{cid}/turns/pro-02.md':
                                  f'DECISION: GO\nTARGET-BRANCH: aa/case-{cid}\nTARGET-COMMIT: {sha}\n'
                                  f'TURN-COMPLETE: {cid}/02\n'})
        self.env.run()
        c = self.env.db.case(cid)
        self.assertEqual((c['phase'], c['pro_turn']), ('WAIT_PRO', 3))
        turn3 = sh(self.env.case_origin, 'git', 'show', f'case/{cid}:cases/{cid}/PRO-TURN-03.md')
        self.assertIn('not at the declared TARGET-COMMIT', turn3)
        self.assertNotEqual(self.env.db.task(tid)['status'], 'DONE')

    def test_failed_push_after_local_fix_does_not_complete(self):
        def fix(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text('ok')
            return Result(True, 'fixed', None, [lane.model])
        tid, cid = self.start({'opus': challenger('AGREE'), 'astra': challenger('AGREE'), 'fix': fix})
        self.draft(cid)
        self.env.run()
        base = self.env.db.task(tid)['base_ref']
        sha = self.env.pro_implement(f'aa/case-{cid}', base, {'app.py': 'print(2)\n'})
        hook = self.env.target_origin / 'hooks' / 'pre-receive'
        hook.write_text('#!/bin/sh\necho rejected >&2\nexit 1\n')
        hook.chmod(0o755)
        self.env.pro_commit(cid, {f'cases/{cid}/turns/pro-02.md':
                                  f'DECISION: GO\nTARGET-BRANCH: aa/case-{cid}\nTARGET-COMMIT: {sha}\n'
                                  f'TURN-COMPLETE: {cid}/02\n'})
        self.env.run()
        c = self.env.db.case(cid)
        self.assertNotEqual(c['phase'], 'DONE')
        self.assertNotEqual(self.env.db.task(tid)['status'], 'DONE')
        kinds = [r['kind'] for r in self.env.db.q('SELECT kind FROM events WHERE case_id=?', (cid,))]
        self.assertIn('step_error', kinds)

    def test_post_go_design_issue_goes_back_to_pro(self):
        design = lambda lane, cwd, prompt, extra: Result(True, 'DESIGN_ISSUE: schema wrong', None, [lane.model])
        tid, cid = self.start({'opus': challenger('AGREE'), 'astra': challenger('AGREE'), 'fix': design})
        self.draft(cid)
        self.env.run()
        base = self.env.db.task(tid)['base_ref']
        sha = self.env.pro_implement(f'aa/case-{cid}', base, {'app.py': 'print(2)\n'})
        self.env.pro_commit(cid, {f'cases/{cid}/turns/pro-02.md':
                                  f'DECISION: GO\nTARGET-BRANCH: aa/case-{cid}\nTARGET-COMMIT: {sha}\n'
                                  f'TURN-COMPLETE: {cid}/02\n'})
        self.env.run()
        c = self.env.db.case(cid)
        self.assertEqual((c['phase'], c['pro_turn']), ('WAIT_PRO', 3))
        turn3 = sh(self.env.case_origin, 'git', 'show', f'case/{cid}:cases/{cid}/PRO-TURN-03.md')
        self.assertIn('Post-GO verification failed', turn3)


class SemIfClientTests(unittest.TestCase):
    """aa.semif.SemIf against a real Unix-socket HTTP server speaking the server protocol."""

    def setUp(self):
        import socketserver
        import threading
        from http.server import BaseHTTPRequestHandler
        self._tmp = tempfile.TemporaryDirectory()
        self.sock = str(Path(self._tmp.name) / 's.sock')
        self.reply = None

        test = self

        class H(BaseHTTPRequestHandler):
            def address_string(self):
                return 'unix'

            def log_message(self, *a):
                pass

            def _send(self, body):
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                self._send({'ok': True, 'model': {}})

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                ids = [o['id'] for o in req['options']]
                self._send(test.reply(ids) if test.reply else
                           {'option_ids': ids, 'probabilities': [0.7] + [0.3 / (len(ids) - 1)] * (len(ids) - 1)})

        class S(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True

        self.server = S(self.sock, H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        from aa.semif import SemIf
        cfg = config.load(Path('/nonexistent'), {'semif': {'socket': self.sock}})
        self.db = DB(':memory:')
        self.semif = SemIf(cfg, self.db)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self._tmp.cleanup()

    def test_choose_logs_decision_with_probabilities(self):
        pick, probs, did = self.semif.choose('tier', 't1', 'state', 'q?', {'a': 'A', 'b': 'B'})
        self.assertEqual(pick, 'a')
        self.assertAlmostEqual(sum(probs.values()), 1.0)
        row = self.db.q('SELECT * FROM decisions WHERE id=?', (did,))[0]
        self.assertEqual((row['kind'], row['proposed']), ('tier', 'a'))

    def test_mismatched_options_are_rejected_as_no_vote(self):
        self.reply = lambda ids: {'option_ids': ['zzz'] + ids[1:], 'probabilities': [0.5, 0.5]}
        pick, probs, _ = self.semif.choose('tier', 't1', 'state', 'q?', {'a': 'A', 'b': 'B'})
        self.assertEqual((pick, probs), (None, None))
        kinds = [r['kind'] for r in self.db.q('SELECT kind FROM events')]
        self.assertIn('decider_error', kinds)

    def test_missing_socket_means_unavailable(self):
        from aa.semif import SemIf
        cfg = config.load(Path('/nonexistent'), {'semif': {'socket': '/nonexistent/s.sock'}})
        s = SemIf(cfg, self.db)
        self.assertFalse(s.available())
        self.assertEqual(s.choose('peer', None, 'x', 'q', {'a': 'A', 'b': 'B'})[0], None)

    def test_rank_orders_by_relevance(self):
        self.reply = lambda ids: {'option_ids': ids, 'probabilities': [0.9, 0.1]}
        ranked = self.semif.rank('t1', 'task', 'relevant?', ['a.py', 'b.py'], 1)
        self.assertEqual(len(ranked), 1)


class WorkerTests(unittest.TestCase):
    def cfg(self, tmp):
        return config.load(Path('/nonexistent'), {'paths': {'state_dir': tmp}})

    def test_claude_model_substitution_is_an_error(self):
        out = json.dumps({'result': 'ok', 'is_error': False, 'modelUsage': {'claude-sonnet-5': {}}})
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, out, ''))
        with tempfile.TemporaryDirectory() as tmp:
            w = Workers(self.cfg(tmp), runner=runner)
            w.verify_billing = lambda cli: None
            r = w.execute(LANES['opus_high'], 'p', Path(tmp))
        self.assertFalse(r.ok)
        self.assertIn('model substitution', r.error)

    def test_child_env_scrubs_api_keys(self):
        from aa.workers import child_env
        with mock.patch.dict('os.environ', {'OPENAI_API_KEY': 'x', 'ANTHROPIC_API_KEY': 'y',
                                            'ANTHROPIC_BASE_URL': 'z', 'CLAUDECODE': '1', 'HOME': '/h'}):
            env = child_env()
        for k in ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL', 'CLAUDECODE'):
            self.assertNotIn(k, env)

    def test_claude_billing_requires_subscription(self):
        status = json.dumps({'loggedIn': True, 'authMethod': 'api_key'})
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, status, ''))
        with tempfile.TemporaryDirectory() as tmp:
            w = Workers(self.cfg(tmp), runner=runner)
            from aa.workers import BillingError
            with self.assertRaises(BillingError):
                w.verify_billing('claude')

    def test_claude_sandbox_mode_uses_auto_and_restricts_writes(self):
        out = json.dumps({'result': 'ok', 'is_error': False, 'modelUsage': {'claude-opus-5-5': {}}})
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, out, ''))
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config.load(Path('/nonexistent'), {'paths': {'state_dir': tmp},
                                                     'workers': {'claude_sandbox': True}})
            w = Workers(cfg, runner=runner)
            w.verify_billing = lambda cli: None
            self.assertTrue(w.execute(LANES['opus_high'], 'p', Path(tmp)).ok)
        cmd = runner.call_args[0][0]
        self.assertIn('--strict-mcp-config', cmd)
        self.assertEqual(cmd[cmd.index('--permission-mode') + 1], 'auto')
        settings = json.loads(cmd[cmd.index('--settings') + 1])['sandbox']
        self.assertTrue(settings['failIfUnavailable'])
        self.assertEqual(settings['filesystem']['allowWrite'], [tmp])
        self.assertIn('~/.ssh', settings['filesystem']['denyRead'])

    def test_claude_default_guard_is_auto_mode_without_blanket_bash(self):
        out = json.dumps({'result': 'ok', 'is_error': False, 'modelUsage': {'claude-opus-5-5': {}}})
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, out, ''))
        with tempfile.TemporaryDirectory() as tmp:
            w = Workers(self.cfg(tmp), runner=runner)
            w.verify_billing = lambda cli: None
            self.assertTrue(w.execute(LANES['opus_high'], 'p', Path(tmp)).ok)
        cmd = runner.call_args[0][0]
        self.assertEqual(cmd[cmd.index('--permission-mode') + 1], 'auto')
        allowed = cmd[cmd.index('--allowedTools') + 1:]
        self.assertNotIn('Bash', allowed, 'Bash goes through the auto-mode classifier, not a blanket allow')
        deny = json.loads(cmd[cmd.index('--settings') + 1])['permissions']['deny']
        self.assertIn('Bash(git push:*)', deny)
        self.assertIn('Read(~/.ssh/**)', deny)

    def test_missing_sandbox_blocks_instead_of_running_unsandboxed(self):
        from aa.workers import BillingError
        runner = mock.Mock(return_value=subprocess.CompletedProcess(
            [], 1, '', 'Error: sandbox required but unavailable: socat not installed'))
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config.load(Path('/nonexistent'), {'paths': {'state_dir': tmp},
                                                     'workers': {'claude_sandbox': True}})
            w = Workers(cfg, runner=runner)
            w.verify_billing = lambda cli: None
            with self.assertRaises(BillingError):
                w.execute(LANES['opus_high'], 'p', Path(tmp))

    def test_codex_auth_rejection_raises_billing_error_not_retry(self):
        from aa.workers import BillingError
        out = '{"type":"turn.failed","error":{"message":"unexpected status 401 Unauthorized: Incorrect API key provided"}}'
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 1, out, ''))
        with tempfile.TemporaryDirectory() as tmp:
            w = Workers(self.cfg(tmp), runner=runner)
            w.verify_billing = lambda cli: None
            with self.assertRaises(BillingError):
                w.execute(LANES['luna_high'], 'p', Path(tmp))

    def test_codex_command_is_subscription_exec_with_effort(self):
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        with tempfile.TemporaryDirectory() as tmp:
            w = Workers(self.cfg(tmp), runner=runner)
            w.verify_billing = lambda cli: None
            w.execute(LANES['luna_low'], 'p', Path(tmp), write=False)
        cmd = runner.call_args[0][0]
        self.assertIn('gpt-6-luna', cmd)
        self.assertIn('model_reasoning_effort="low"', cmd)
        self.assertIn('read-only', cmd)


if __name__ == '__main__':
    unittest.main()


class FailureTriageTests(unittest.TestCase):
    """aa/failure_triage.py prototype: deterministic rerun/base steps, decider only for env-vs-code."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.wt = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, command, base_ok=True, base_out='', decider_pick='code'):
        from aa import checks as ck
        from aa.failure_triage import triage
        failed = ck.run({'c': command}, self.wt)[0]
        base = lambda cmd: ck.CheckRun('base', cmd, 0 if base_ok else 1, base_out)
        return triage(failed, self.wt, base, FakeCLM(peer=decider_pick))   # non-tier kinds use .peer

    def test_flaky_passes_on_rerun(self):
        (self.wt / 'flag').unlink(missing_ok=True)
        v = self._run('test -f flag || { touch flag; exit 1; }')
        self.assertEqual(v.action, 'FLAKY')

    def test_pre_existing_failure_on_base(self):
        v = self._run('echo "Error: legacy broken"; exit 1', base_ok=False, base_out='Error: legacy broken\n')
        self.assertEqual(v.action, 'PRE_EXISTING')

    def test_environment_needs_confident_decider(self):
        self.assertEqual(self._run('echo "connection refused"; exit 1', decider_pick='environment').action,
                         'ENVIRONMENT')
        self.assertEqual(self._run('echo "AssertionError"; exit 1', decider_pick='code').action, 'CODE')


class QualityTests(unittest.TestCase):
    """Oracle tests, mutation gate and best-of-2 (aa/quality.py) through the real task flow."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self.env.close()
        self._tmp.cleanup()

    def events(self, tid):
        return [(r['kind'], json.loads(r['detail'])) for r in
                self.env.db.q('SELECT kind, detail FROM events WHERE task_id=? ORDER BY id', (tid,))]

    def test_oracle_tests_by_other_vendor_become_required_and_ship(self):
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=True), 'work': write_done,
                                  'oracle': oracle_writer()}, FakeCLM('bounded'), oracle=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        oracle_calls = [c for c in self.env.workers.calls if c[1].endswith('-oracle')]
        self.assertEqual(oracle_calls[0][0], 'opus_medium', 'Luna implements -> Anthropic writes the tests')
        self.assertIn('oracle_tests', t['data']['checks'])
        shipped = sh(self.env.target, 'git', 'show', f'aa/{tid}:tests/check_feature.sh')
        self.assertIn('test -f done.txt', shipped)
        self.assertEqual(sh(self.env.target, 'git', 'show', f'aa/{tid}:app.py'), 'print(1)',
                         'oracle author cannot change production code')
        self.assertFalse((self.env.cfg.worktrees / f'{tid}-oracle').exists())

    def test_oracle_rejected_when_it_passes_on_base(self):
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=True), 'work': write_done,
                                  'oracle': oracle_writer(body='true\n')}, FakeCLM('bounded'), oracle=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertNotIn('oracle_tests', t['data']['checks'])
        self.assertIn(('oracle_rejected', {'reason': 'tests already pass on the base commit'}), self.events(tid))

    def test_untestable_task_gets_no_oracle(self):
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=False), 'work': write_done},
                       FakeCLM('bounded'), oracle=True)
        tid = self.env.app.tasks.create(self.env.target, 'docs')
        self.env.run()
        self.assertFalse([c for c in self.env.workers.calls if c[1].endswith('-oracle')])

    def test_worker_edits_to_oracle_are_reverted_and_reported(self):
        judged = []

        def cheat(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text('ok')
            (cwd / 'tests' / 'check_feature.sh').write_text('true\n')
            return Result(True, 'done', None, [lane.model])

        def judge(lane, cwd, prompt, extra):
            judged.append(prompt)
            return Result(True, '', spec_verdict([]), [lane.model])
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=True), 'work': cheat, 'spec': judge,
                                  'oracle': oracle_writer()}, FakeCLM('bounded'), oracle=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        self.assertIn('oracle_tamper', [k for k, _ in self.events(tid)])
        self.assertIn('modified the independent acceptance tests', judged[0])
        self.assertIn('test -f done.txt', sh(self.env.target, 'git', 'show', f'aa/{tid}:tests/check_feature.sh'))

    def test_mutation_gate_flags_weak_oracle_to_judge(self):
        judged = []

        def impl(lane, cwd, prompt, extra):
            (cwd / 'calc2.py').write_text('def f():\n    return 3 - 1\n')
            (cwd / 'done.txt').write_text('ok')
            return Result(True, 'done', None, [lane.model])

        def judge(lane, cwd, prompt, extra):
            judged.append(prompt)
            return Result(True, '', spec_verdict([]), [lane.model])
        weak = oracle_writer(body='python3 -c "import calc2; assert calc2.f() > 0"\n')
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=True), 'work': impl, 'spec': judge,
                                  'oracle': weak}, FakeCLM('bounded'), oracle=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        m = self.env.db.task(tid)['data']['mutation']
        self.assertEqual((m['killed'], m['total']), (0, 1))
        self.assertIn('independent acceptance tests are weak', judged[0])

    def _race_env(self, work, pick=None, tier='medium_tough'):
        script = {'triage': triage(tier), 'work': work}
        if pick:
            script['pick'] = pick
        self.env = Env(self.tmp, script, FakeCLM(tier, peer='astra'), best_of_2=True)
        return self.env.app.tasks.create(self.env.target, 'medium task')

    def test_race_resumes_selection_without_rerunning_workers(self):
        def pick(lane, cwd, prompt, extra):
            raise RuntimeError('judge crashed')
        tid = self._race_env(self._both_pass, pick)
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertEqual(len([c for c in self.env.workers.calls if '-race-' in c[1]]), 2, 'race ran once')
        self.assertIn('pick_judge_error', [r['kind'] for r in self.env.db.q('SELECT kind FROM events')])

    def test_race_checks_decide_winner(self):
        def work(lane, cwd, prompt, extra):
            if lane.name == 'astra_high':
                (cwd / 'done.txt').write_text('ok')
            return Result(True, 'done', None, [lane.model])
        tid = self._race_env(work)
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['lane']), ('DONE', 'astra_high'))
        self.assertEqual(sorted(c[0] for c in self.env.workers.calls if '-race-' in c[1]),
                         ['astra_high', 'opus_high'])
        self.assertFalse((self.env.cfg.worktrees / f'{tid}-opus_high').exists())
        self.assertIn(f'aa/{tid}', sh(self.env.target_origin, 'git', 'branch', '--list'))
        row = self.env.db.q("SELECT final FROM decisions WHERE kind='best_of_2' AND task_id=?", (tid,))[0]
        self.assertEqual(row['final'], 'astra_high')

    def _both_pass(self, lane, cwd, prompt, extra):
        (cwd / 'done.txt').write_text(f'implemented by {lane.name}' + (' with extra care' * 5 if 'opus' in lane.name else ''))
        return Result(True, 'done', None, [lane.model])

    def test_race_judges_agree(self):
        def pick(lane, cwd, prompt, extra):
            a_is_opus = prompt.index('opus_high') < prompt.index('astra_high')
            return Result(True, '', {'winner': 'A' if a_is_opus else 'B', 'reason': 'opus better'}, [lane.model])
        tid = self._race_env(self._both_pass, pick)
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['lane'], 'opus_high')
        self.assertEqual(set(t['data']['pick_votes'].values()), {'opus_high'})

    def test_race_judges_split_uses_tiebreak(self):
        def pick(lane, cwd, prompt, extra):          # each judge prefers its own vendor
            mine = 'opus_high' if 'opus' in lane.name else 'astra_high'
            a_is_mine = prompt.index(mine) < prompt.index('astra_high' if mine == 'opus_high' else 'opus_high')
            return Result(True, '', {'winner': 'A' if a_is_mine else 'B', 'reason': 'mine'}, [lane.model])
        tid = self._race_env(self._both_pass, pick)
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['lane'], 'astra_high', 'split -> smaller diff wins')
        self.assertIn('judges split', t['data']['race_winner']['reason'])

    def test_luna_failure_escalates_to_race(self):
        def work(lane, cwd, prompt, extra):
            if lane.name == 'opus_high':
                (cwd / 'done.txt').write_text('ok')
            return Result(True, 'done', None, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': work}, FakeCLM('bounded'),
                       best_of_2=True, triage=False)
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['lane']), ('DONE', 'opus_high'))
        lanes = [c[0] for c in self.env.workers.calls if not c[1].endswith(('-triage', '-spec'))]
        self.assertEqual(lanes[:2], ['luna_high', 'luna_high'])
        self.assertIn(('escalate', {'frm': 'luna_high', 'to': 'best_of_2'}), self.events(tid))


class OracleValidationTests(unittest.TestCase):
    """Regressions from the live run t0926-9f9b9: a syntax-broken oracle escalated to Pro."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self.env.close()
        self._tmp.cleanup()

    def events(self, tid):
        return [(r['kind'], json.loads(r['detail'])) for r in
                self.env.db.q('SELECT kind, detail FROM events WHERE task_id=? ORDER BY id', (tid,))]

    def py_oracle(self, bodies):
        calls = []

        def fn(lane, cwd, prompt, extra):
            calls.append(prompt)
            (cwd / 'tests').mkdir(exist_ok=True)
            (cwd / 'tests' / 'test_feature.py').write_text(bodies[min(len(calls), len(bodies)) - 1])
            return Result(True, '{}', {'test_files': ['tests/test_feature.py'],
                                       'command': 'python3 tests/test_feature.py', 'notes': ''}, [lane.model])
        return fn, calls

    GOOD = 'import os, sys\nsys.exit(0 if os.path.exists("done.txt") else 1)\n'
    BROKEN = 'def test_un-grouped():\n    pass\n'

    def test_syntax_error_gets_one_repair_round(self):
        oracle, calls = self.py_oracle([self.BROKEN, self.GOOD])
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=True), 'work': write_done, 'oracle': oracle},
                       FakeCLM('bounded'), oracle=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertEqual(len(calls), 2)
        self.assertIn('previous tests were rejected: invalid test file', calls[1])
        self.assertIn('oracle_tests', t['data']['checks'])

    def test_unrepairable_oracle_is_skipped(self):
        oracle, calls = self.py_oracle([self.BROKEN, self.BROKEN])
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=True), 'work': write_done, 'oracle': oracle},
                       FakeCLM('bounded'), oracle=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], len(calls)), ('DONE', 2))
        self.assertNotIn('oracle_tests', t['data']['checks'])

    def test_race_drops_disputed_oracle_instead_of_escalating(self):
        impossible = 'import sys\nsys.exit(1)  # buggy oracle that can never pass\n'
        oracle, _ = self.py_oracle([impossible])

        def work(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text(lane.name)
            return Result(True, '{}', {'status': 'done', 'summary': 'implemented', 'open_items': [], 'question': '',
                                       'rebuttals': ['tests/test_feature.py always exits 1; the acceptance test is wrong']},
                          [lane.model])
        self.env = Env(self.tmp, {'triage': triage('medium_tough', testable=True), 'work': work, 'oracle': oracle},
                       FakeCLM('medium_tough'), oracle=True, best_of_2=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertIsNone(t['case_id'])
        self.assertIn('oracle_dropped', [k for k, _ in self.events(tid)])
        self.assertNotIn('oracle_tests', t['data']['checks'])


class LocalModelTests(unittest.TestCase):
    """Gemma (local lane) as extra independent test writer and as neutral tie-breaker."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self.env.close()
        self._tmp.cleanup()

    @staticmethod
    def oracle_both(local_files):
        def fn(lane, cwd, prompt, extra):
            if lane.cli == 'local':
                return Result(True, '{}', {'files': local_files, 'command': 'sh tests/check_indep.sh', 'notes': ''},
                              [lane.model])
            return oracle_writer()(lane, cwd, prompt, extra)
        return fn

    def test_single_lane_gets_extra_local_test_set(self):
        files = [{'path': 'tests/check_indep.sh', 'content': 'test -f done.txt\n'},
                 {'path': '../escape_test.sh', 'content': 'x'},
                 {'path': 'tests/check_feature.sh', 'content': 'true\n'}]          # exists: must not overwrite
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=True), 'work': write_done, 'local': True,
                                  'oracle': self.oracle_both(files)}, FakeCLM('bounded'), oracle=True, local=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertEqual(t['data']['oracle']['authors'], ['opus_medium', 'gemma_local'])
        self.assertEqual(sorted(t['data']['oracle']['files']), ['tests/check_feature.sh', 'tests/check_indep.sh'])
        self.assertIn('test -f done.txt', sh(self.env.target, 'git', 'show', f'aa/{tid}:tests/check_feature.sh'))
        self.assertFalse((self.tmp / 'state' / 'worktrees' / 'escape_test.sh').exists())

    def test_race_tests_written_by_local_model(self):
        files = [{'path': 'tests/check_indep.sh', 'content': 'test -f done.txt\n'}]
        self.env = Env(self.tmp, {'triage': triage('medium_tough', testable=True), 'work': write_done, 'local': True,
                                  'oracle': self.oracle_both(files)}, FakeCLM('medium_tough'), oracle=True,
                       best_of_2=True, local=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertEqual(t['data']['oracle']['authors'], ['gemma_local'])

    def _split_env(self, tiebreak_pick):
        def work(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text(f'{lane.name}' + (' long' * 20 if 'opus' in lane.name else ''))
            return Result(True, 'done', None, [lane.model])

        def pick(lane, cwd, prompt, extra):
            if lane.cli == 'local':
                return tiebreak_pick(prompt, lane)
            mine = 'opus_high' if 'opus' in lane.name else 'astra_high'
            other = 'astra_high' if mine == 'opus_high' else 'opus_high'
            return Result(True, '', {'winner': 'A' if prompt.index(mine) < prompt.index(other) else 'B',
                                     'reason': 'mine'}, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('medium_tough'), 'work': work, 'pick': pick, 'local': True},
                       FakeCLM('medium_tough'), best_of_2=True, local=True)
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(60)
        return self.env.db.task(tid)

    def test_split_panel_resolved_by_consistent_local_tiebreak(self):
        def prefers_opus(prompt, lane):
            a_opus = prompt.index('opus_high') < prompt.index('astra_high')
            return Result(True, '', {'winner': 'A' if a_opus else 'B', 'reason': 'opus'}, [lane.model])
        t = self._split_env(prefers_opus)
        self.assertEqual(t['lane'], 'opus_high', 'consistent tie-break beats the smaller-diff default')
        self.assertIn('tie-break by gemma_local', t['data']['race_winner']['reason'])

    def test_position_biased_tiebreak_is_ignored(self):
        always_a = lambda prompt, lane: Result(True, '', {'winner': 'A', 'reason': 'first'}, [lane.model])
        t = self._split_env(always_a)
        self.assertEqual(t['lane'], 'astra_high', 'inconsistent across orders -> smaller diff')
        self.assertEqual(len(set(t['data']['tiebreak_votes'])), 2)
