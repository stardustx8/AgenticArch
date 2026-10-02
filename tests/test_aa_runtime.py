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

    def execute(self, lane, prompt, cwd, *, write=True, extra_dirs=(), schema=None, log_name='job', web=False):
        self.verify_billing(lane.cli)
        self.calls.append((lane.name, log_name))
        self.web_calls = getattr(self, 'web_calls', []) + ([log_name] if web else [])
        if log_name.endswith('-triage'):
            if self.script['triage'] is None:
                return Result(False, '', None, [], error='triage timeout')
            return Result(True, '', self.script['triage'], [lane.model])
        kind = _kind(log_name)
        if kind == 'spec' and 'spec' not in self.script:
            return Result(True, '', _complete_verdict(spec_verdict([]), prompt), [lane.model])   # all met
        if kind == 'conf' and 'conf' not in self.script:
            return Result(True, '', {'ambiguities': [], 'unverified': [], 'probability': 0.9}, [lane.model])
        if kind == 'pick' and 'pick' not in self.script:
            return Result(True, '', {'winner': 'A', 'reason': 'default'}, [lane.model])
        fn = self.script[kind]
        res = fn(lane, Path(cwd), prompt, extra_dirs)
        if kind == 'spec' and res.structured:
            res.structured = _complete_verdict(res.structured, prompt)
        return res


def _complete_verdict(verdict: dict, prompt: str) -> dict:
    """Scripted spec verdicts cover criterion 1; the coordinator always appends 'the task as written',
    so unscripted indices are answered as met (a scripted verdict never has to know the count)."""
    import re as _re
    n = max([int(m) for m in _re.findall(r'^(\d+)\. ', prompt.split('Acceptance criteria', 1)[-1], _re.M)] or [1])
    have = {c.get('index') for c in verdict.get('criteria', [])}
    if not have or verdict.get('exact'):   # empty or explicitly exact verdicts stay as they are
        return {k: v for k, v in verdict.items() if k != 'exact'}
    extra = [{'index': i, 'criterion': 'auto', 'met': True, 'reason': 'ok'} for i in range(max(have) + 1, n + 1)]
    return dict(verdict, criteria=list(verdict.get('criteria', [])) + extra)


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
    if log_name.endswith('-conf'):
        return 'conf'
    if log_name.endswith('-research'):
        return 'research'
    if log_name.endswith('-oracle'):
        return 'oracle'
    if log_name.endswith('-map'):
        return 'map'
    if log_name.endswith('-attack'):
        return 'attack'
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


LUNA_TIER_LANES = {'routine': 'luna_high', 'bounded': 'luna_high'}


class Env:
    def __init__(self, tmp: Path, script: dict, clm: FakeCLM, checks='test -f done.txt', policy='codex',
                 triage=True, oracle=False, best_of_2=False, local=False, ideas=None, spec=True,
                 tier_lanes=LUNA_TIER_LANES, confidence=False, research=False):
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
            'spec_check': {'enabled': spec},     # most flow tests exercise the judge (off by default, D024)
            'confidence_check': {'enabled': confidence},
            'research_phase': {'offer': research},        # the test repos are tiny "new projects"; most tests skip it
            'oracle_tests': {'enabled': oracle},
            'best_of_2': {'enabled': best_of_2},
            'local_llm': {'enabled': local, 'url': 'http://127.0.0.1:9'},   # never a real server
            'ideas': ideas or {},
            # The flow tests exercise the Luna ladder (race on escalation); the Opus default (D028) has its own tests.
            **({'tier_lanes': dict(tier_lanes)} if tier_lanes is not None else {}),
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
        self.env.cfg.data['tier_lanes']['routine'] = 'luna_low'      # the low lane still exists when configured (D027)
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
        self.env.cfg.data['tier_lanes']['routine'] = 'luna_low'      # exercises luna_low -> luna_high (D027)
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
        self.assertIn('does exactly what the task statement above asks, as written', prompts[0])

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

    def _answer_every_question(self, tid, rounds=30):
        answers = 0
        for _ in range(rounds):
            self.env.run()
            t = self.env.db.task(tid)
            if t['status'] != 'WAIT_OWNER':
                break
            answers += 1
            self.env.db.inbox_put(f'answer {tid} no more information, decide yourself')
        return self.env.db.task(tid), answers

    def test_ever_blocking_worker_does_not_loop_on_the_owner(self):
        # Lab run b3_allocate_remainder: 48 owner pings, because answers are free reruns.
        always = lambda lane, cwd, prompt, extra: Result(True, '{}', {
            'status': 'blocked', 'summary': 'stopped', 'open_items': [], 'question': 'Which rounding?',
            'rebuttals': []}, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': always}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        t, answers = self._answer_every_question(tid)
        self.assertEqual(answers, 3)
        self.assertNotIn(t['status'], ('WAIT_OWNER', 'READY', 'VERIFY'))
        self.assertIn('owner_questions_exhausted', [r['kind'] for r in self.env.db.q(
            'SELECT kind FROM events WHERE task_id=?', (tid,))])

    def test_model_call_cap_blocks_a_runaway_task_and_retry_resets_it(self):
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': noop}, FakeCLM('routine'))
        self.env.cfg['retry']['max_model_calls'] = 3
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'BLOCKED')
        self.assertIn('3 model calls', t['result'])
        self.assertEqual(len(self.env.workers.calls), 3)            # triage, worker, spec judge
        self.assertIn('probably a loop', self.env.sent[-1][1])
        self.env.db.inbox_put(f'retry {tid}')
        self.env.run()
        self.assertGreater(len(self.env.workers.calls), 3, 'a retry gets a fresh budget')
        self.assertNotEqual(self.env.db.task(tid)['status'], 'BLOCKED')

    def test_triage_stops_asking_after_the_question_cap(self):
        asking = dict(triage('routine'), owner_question='Which exchange rate?')
        self.env = Env(self.tmp, {'triage': asking, 'work': write_done}, FakeCLM('routine'))
        tid = self.env.app.tasks.create(self.env.target, 'convert usd')
        t, answers = self._answer_every_question(tid)
        self.assertEqual((t['status'], answers), ('DONE', 3))

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

    def test_local_model_truncated_output_is_a_failure(self):
        import io
        body = json.dumps({'choices': [{'finish_reason': 'stop', 'stop_reason': 'repetition_detected',
                                        'message': {'content': 'a-b-a-b-a-b'}}]})
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch('urllib.request.urlopen', return_value=io.BytesIO(body.encode())):
            w = Workers(self.cfg(tmp))
            w.verify_billing = lambda cli: None
            r = w.execute(LANES['gemma_local'], 'p', Path(tmp), write=False, schema={'type': 'object'})
        self.assertFalse(r.ok)
        self.assertIn('degenerated', r.error)

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
        self.assertIn('memories.use_memories=false', cmd)   # D024: personal memories stay out

    def test_codex_memories_flags_can_be_turned_off(self):
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self.cfg(tmp); cfg.data['workers']['codex_no_memories'] = False
            w = Workers(cfg, runner=runner)
            w.verify_billing = lambda cli: None
            w.execute(LANES['luna_low'], 'p', Path(tmp), write=False)
        self.assertNotIn('features.memories=false', runner.call_args[0][0])


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
        self.assertIn('independent acceptance tests may be weak', judged[0])

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

    # Lab runs b2_ledger_reversals_idempotency / b3_path_parent_segments: a wrong local test set,
    # also run by the repo's own test command, blocked the task until it escalated to Pro.
    SUITE = 'test -f done.txt && for f in tests/*.sh; do [ -e $f ] || continue; sh $f || exit 1; done'

    @staticmethod
    def wrong_local_set(lane, cwd, prompt, extra):
        if lane.cli == 'local':
            return Result(True, 'FILE: tests/check_indep.sh\n```sh\nexit 1\n```\nCOMMAND: sh tests/check_indep.sh\n',
                          None, [lane.model])
        return oracle_writer()(lane, cwd, prompt, extra)

    @staticmethod
    def disputing_worker(status):
        def work(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text(lane.name)
            item = 'tests/check_indep.sh can never pass; it contradicts the task and is read-only for me'
            return Result(True, '{}', {'status': status, 'summary': 'implemented', 'rebuttals': [],
                                       'open_items': [item] if status == 'partial' else [],
                                       'question': item if status == 'blocked' else ''}, [lane.model])
        return work

    def test_single_lane_drops_only_the_disputed_test_set(self):
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=True), 'local': True,
                                  'work': self.disputing_worker('partial'), 'oracle': self.wrong_local_set},
                       FakeCLM('bounded'), checks=self.SUITE, oracle=True, local=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['case_id']), ('DONE', None))
        self.assertEqual(t['data']['oracle']['authors'], ['opus_medium'])      # the valid set stays a check
        self.assertIn('oracle_tests', t['data']['checks'])
        files = sh(self.env.target, 'git', 'ls-tree', '-r', '--name-only', f'aa/{tid}')
        self.assertIn('tests/check_feature.sh', files)
        self.assertNotIn('tests/check_indep.sh', files)
        self.assertFalse([s for s in self.env.sent if 'Question' in s[0]], 'no owner ping for a test dispute')

    def test_race_blocked_on_wrong_tests_drops_them(self):
        self.env = Env(self.tmp, {'triage': triage('medium_tough', testable=True), 'local': True,
                                  'work': self.disputing_worker('blocked'), 'oracle': self.wrong_local_set},
                       FakeCLM('medium_tough'), checks=self.SUITE, oracle=True, best_of_2=True, local=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['case_id']), ('DONE', None))
        self.assertIsNone(t['data']['oracle'])
        self.assertNotIn('tests/check_indep.sh', sh(self.env.target, 'git', 'ls-tree', '-r', '--name-only', f'aa/{tid}'))

    def test_undisputed_oracle_failure_still_goes_back_to_the_worker(self):
        self.env = Env(self.tmp, {'triage': triage('bounded', testable=True), 'local': True,
                                  'work': self.disputing_worker('done'), 'oracle': self.wrong_local_set},
                       FakeCLM('bounded'), checks=self.SUITE, oracle=True, local=True)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertNotEqual(t['status'], 'DONE')
        self.assertNotIn('oracle_dropped', [k for k, _ in self.events(tid)])


class ContextSelectionTests(unittest.TestCase):
    """Deep-case reading list: triage paths first, then BM25 over contents (not path words)."""

    def test_reading_list_finds_files_by_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            files = {'app.py': 'print(1)\n', 'billing/fx.py': 'def convert(amount, exchange_rate):\n'
                     '    """Currency conversion with the daily exchange rate; rounding half up."""\n',
                     'img.bin': '\0' * 10 + 'exchange rate', 'docs/notes.md': 'meeting notes\n'}
            files.update({f'pkg/mod{i}.py': f'def f{i}(): return {i}\n' for i in range(30)})
            env = Env(tmp, {'triage': triage('tough'), 'work': noop}, FakeCLM('tough'))
            init_repo(tmp / 'big', files)
            t = {'id': 't0926-00000', 'prompt': 'Fix the rounding of the exchange rate conversion'}
            paths = env.app.cases._context_paths(t, tmp / 'big', {'relevant_paths': ['app.py', 'nope.py']})
            env.close()
        self.assertEqual(paths[0], 'app.py', 'triage paths stay pinned first')
        self.assertEqual(paths[1], 'billing/fx.py')
        self.assertNotIn('img.bin', paths)
        self.assertLessEqual(len(paths), 12)


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
                text = ''.join(f"FILE: {f['path']}\n```sh\n{f['content'].rstrip()}\n```\n\n" for f in local_files)
                return Result(True, text + 'COMMAND: sh tests/check_indep.sh\n', None, [lane.model])
            return oracle_writer()(lane, cwd, prompt, extra)
        return fn

    def test_parse_fenced_files(self):
        from aa.quality import parse_fenced_files
        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': write_done}, FakeCLM('routine'))
        text = ('Here are the tests.\nFILE: tests/test_a_indep.py\n```python\nimport x\n\ndef test():\n    '
                'assert x\n```\nFILE: `tests/test_b_indep.py`\n```\npass\n```\nCOMMAND: `python3 -m pytest -q`\n')
        files, cmd = parse_fenced_files(text)
        self.assertEqual([f['path'] for f in files], ['tests/test_a_indep.py', 'tests/test_b_indep.py'])
        self.assertIn('def test():', files[0]['content'])
        self.assertEqual(cmd, 'python3 -m pytest -q')

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


class IdeaFlagTests(unittest.TestCase):
    """Experimental ideas (config 'ideas'), each off by default and testable in the lab."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self.env.close()
        self._tmp.cleanup()

    def _run(self, script, ideas, **kw):
        prompts = {'work': [], 'spec': []}

        def work(lane, cwd, prompt, extra):
            prompts['work'].append(prompt)
            return script.get('work', write_done)(lane, cwd, prompt, extra)

        def judge(lane, cwd, prompt, extra):
            prompts['spec'].append(prompt)
            return Result(True, '', spec_verdict([]), [lane.model])
        full = {'triage': triage('bounded'), 'work': work, 'spec': judge, **{k: v for k, v in script.items() if k != 'work'}}
        self.env = Env(self.tmp, full, FakeCLM('bounded'), ideas=ideas, **kw)
        tid = self.env.app.tasks.create(self.env.target, 'fix the bug')
        self.env.run(60)
        return self.env.db.task(tid), prompts

    def test_all_ideas_off_by_default(self):
        t, p = self._run({}, {})
        self.assertEqual(t['status'], 'DONE')
        self.assertNotIn('Order of authority', p['work'][0])
        self.assertNotIn('defect pattern', p['work'][0])

    def test_authority_order_and_defect_twins_reach_the_worker(self):
        t, p = self._run({}, {'authority_order': True, 'defect_twins': True})
        self.assertIn('Order of authority', p['work'][0])
        self.assertIn('same defect pattern', p['work'][0])

    def test_spec_conflicts_reach_the_judge(self):
        def work(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text('ok')
            return Result(True, '{}', {'status': 'done', 'summary': 's', 'open_items': [], 'question': '',
                                       'rebuttals': [], 'spec_conflicts': ['test expects 400 but task says 422']},
                          [lane.model])
        t, p = self._run({'work': work}, {'authority_order': True})
        self.assertIn('test expects 400 but task says 422', p['spec'][0])

    def test_impact_map_is_shared_with_worker(self):
        mapper = lambda lane, cwd, prompt, extra: Result(True, '', {'files': ['app.py: entry'], 'symbols': [],
                                                                  'patterns': [], 'pitfalls': ['off by one']},
                                                         [lane.model])
        t, p = self._run({'map': mapper}, {'impact_map': True})
        self.assertEqual(t['status'], 'DONE')
        self.assertIn('off by one', p['work'][0])
        self.assertIn(('luna_low', f'{t["id"]}-map'), self.env.workers.calls)

    def test_diff_audit_flags_debug_prints_and_test_edits(self):
        def work(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text('ok')
            (cwd / 'app.py').write_text('print(1)\nprint("debug")\n')
            (cwd / 'tests').mkdir(exist_ok=True)
            (cwd / 'tests' / 'test_x.py').write_text('x')
            return Result(True, 'done', None, [lane.model])
        t, p = self._run({'work': work}, {'diff_audit': True})
        audit = t['data']['audit']
        self.assertTrue(any('debug statement added in app.py' in a for a in audit), audit)
        self.assertIn('Deterministic diff audit findings', p['spec'][0])

    def test_attacker_failing_test_is_evidence_for_judge(self):
        attack = lambda lane, cwd, prompt, extra: Result(
            True, 'FILE: tests/test_attack_x.py\n```\nimport sys\nsys.exit(1)\n```\nCOMMAND: python3 tests/test_attack_x.py\n',
            None, [lane.model])
        t, p = self._run({'attack': attack, 'local': True}, {'attacker': True}, local=True)
        self.assertEqual(len(t['data']['attack']), 1)
        self.assertIn('adversarial test written by an independent model FAILS', p['spec'][0])
        self.assertFalse((self.env.cfg.worktrees / t['id'] / 'tests' / 'test_attack_x.py').exists())


class NotifyFailureTests(unittest.TestCase):
    """2026-09-27: ntfy answered HTTP 429 for hours and every push was lost unnoticed."""

    def notifier(self):
        from aa.notify import Notifier
        cfg = config.load(Path('/nonexistent'), {'ntfy': {'enabled': True, 'url': 'http://127.0.0.1:9'}})
        n = Notifier(cfg, DB(':memory:'))
        n.retry_delay_s = 0
        return n

    @staticmethod
    def http_error(code):
        import urllib.error
        return urllib.error.HTTPError('http://x', code, 'err', {}, None)

    def test_transient_send_failure_is_retried_once(self):
        n = self.notifier(); calls = []
        class Ok:
            def read(self): return b''
        def urlopen(req, timeout):
            calls.append(1)
            if len(calls) == 1:
                raise self.http_error(429)
            return Ok()
        with mock.patch('urllib.request.urlopen', urlopen):
            n.send('t', 'm')
        self.assertEqual(len(calls), 2)
        self.assertEqual(n.db.q("SELECT COUNT(*) AS c FROM events WHERE kind='notify_failed'")[0]['c'], 0)

    def test_persistent_send_failure_is_recorded_with_title(self):
        n = self.notifier()
        def urlopen(req, timeout):
            raise self.http_error(429)
        with mock.patch('urllib.request.urlopen', urlopen), mock.patch('sys.stderr') as err:
            n.send('Question from worker: t1', 'm')
        row = n.db.q("SELECT detail FROM events WHERE kind='notify_failed'")
        self.assertEqual(len(row), 1)
        self.assertIn('Question from worker: t1', row[0]['detail'])
        self.assertTrue(err.write.called)

    def test_permanent_error_is_not_retried(self):
        n = self.notifier(); calls = []
        def urlopen(req, timeout):
            calls.append(1); raise self.http_error(403)
        with mock.patch('urllib.request.urlopen', urlopen), mock.patch('sys.stderr'):
            n.send('t', 'm')
        self.assertEqual(len(calls), 1)

    def test_reply_poll_outage_is_logged_once_and_recovery_noted(self):
        n = self.notifier()
        def down(req, timeout):
            raise OSError('connection refused')
        class Ok:
            def read(self): return b''
        with mock.patch('urllib.request.urlopen', down), mock.patch('sys.stderr'):
            n.poll_replies(); n.poll_replies(); n.poll_replies()
        with mock.patch('urllib.request.urlopen', lambda req, timeout: Ok()):
            n.poll_replies()
        kinds = [r['kind'] for r in n.db.q("SELECT kind FROM events WHERE kind LIKE 'notify_poll%' ORDER BY id")]
        self.assertEqual(kinds, ['notify_poll_failed', 'notify_poll_recovered'])

    def test_doctor_reports_the_latest_failure_and_fails_only_while_recent(self):
        from aa.cli import notify_health
        db = DB(':memory:')
        self.assertEqual(notify_health(db, 1e9), (True, 'no failures'))
        with mock.patch('time.time', lambda: 1e9 - 7200):
            db.event('notify_failed', title='zzz old', error='429')
        with mock.patch('time.time', lambda: 1e9 - 60):
            db.event('notify_failed', title='aaa new', error='429')
        good, detail = notify_health(db, 1e9)
        self.assertFalse(good)
        self.assertIn('2 failed; latest:', detail)
        self.assertIn('aaa new', detail)
        good, detail = notify_health(db, 1e9 + 3700)
        self.assertTrue(good)
        self.assertIn('aaa new', detail)


class RequestAuthoritativeTests(unittest.TestCase):
    """Lab diag2-4 (2026-09-27): triage paraphrases in the worker prompt dropped a contract detail
    ('every row carries restated: bool') and workers rewrote the contract to fit; without them the
    in-harness worker matched the raw model (8/8 vs 1/8)."""

    CRIT = 'CRIT-XYZ marks only restated months'

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        if hasattr(self, 'env'):
            self.env.close()
        self._tmp.cleanup()

    def tri(self, **kw):
        return dict(triage('bounded', testable=True), acceptance_criteria=[self.CRIT], **kw)

    def test_worker_gets_request_as_authority_and_no_triage_criteria(self):
        prompts = []
        def work(lane, cwd, prompt, extra):
            prompts.append(prompt); return write_done(lane, cwd, prompt, extra)
        self.env = Env(self.tmp, {'triage': self.tri(), 'work': work}, FakeCLM('bounded'))
        self.env.app.tasks.create(self.env.target, 'add the widget exactly as documented')
        self.env.run()
        self.assertIn("The owner's request (authoritative)", prompts[0])
        self.assertIn('add the widget exactly as documented', prompts[0])
        self.assertNotIn(self.CRIT, prompts[0])
        self.assertIn('not a limit on what to read', prompts[0])

    def test_oracle_authors_get_no_triage_criteria(self):
        seen = []
        def oracle(lane, cwd, prompt, extra):
            seen.append(prompt); return oracle_writer()(lane, cwd, prompt, extra)
        self.env = Env(self.tmp, {'triage': self.tri(), 'work': write_done, 'oracle': oracle},
                       FakeCLM('bounded'), oracle=True)
        self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        self.assertTrue(seen)
        self.assertTrue(all(self.CRIT not in p for p in seen))

    def test_spec_judge_always_judges_the_task_as_written_last(self):
        from aa.tasks import TASK_AS_WRITTEN
        prompts = []
        def spec(lane, cwd, prompt, extra):
            prompts.append(prompt); return Result(True, '', spec_verdict([]), [lane.model])
        self.env = Env(self.tmp, {'triage': self.tri(), 'work': write_done, 'spec': spec}, FakeCLM('bounded'))
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        self.assertIn(f'1. {self.CRIT}', prompts[0])
        self.assertIn(f'2. {TASK_AS_WRITTEN}', prompts[0])
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')

    def test_triage_prompt_forbids_invented_requirements(self):
        from aa.tasks import render
        text = render('triage.md', repo='r', prompt='p', owner_answers='')
        self.assertIn('Never add requirements, policies or decisions the task does not ask for', text)
        self.assertIn('Keep exact names, keys, values and scope words', text)

    def _contract_env(self, edit):
        self.env = Env(self.tmp, {'triage': self.tri(), 'work': edit, 'spec': self.spec}, FakeCLM('bounded'))
        (self.env.target / 'docs').mkdir()
        (self.env.target / 'docs' / 'contracts.md').write_text('Rows carry `restated: bool`.\n')
        (self.env.target / 'docs' / 'handoff.md').write_text('notes\n')
        sh(self.env.target, 'git', 'add', '-A'); sh(self.env.target, 'git', 'commit', '-qm', 'docs')
        return self.env.app.tasks.create(self.env.target, 'feature')

    def spec(self, lane, cwd, prompt, extra):
        self.spec_prompts.append(prompt); return Result(True, '', spec_verdict([]), [lane.model])

    def test_rewritten_contract_is_flagged_and_judged_against_the_original(self):
        self.spec_prompts = []
        def edit(lane, cwd, prompt, extra):
            (cwd / 'docs' / 'contracts.md').write_text('Only restated months carry `restated: true`.\n')
            return write_done(lane, cwd, prompt, extra)
        tid = self._contract_env(edit)
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['data']['contract_edits'], ['docs/contracts.md'])
        self.assertIn('Judge the delivery against the ORIGINAL text', self.spec_prompts[0])
        self.assertIn('-Rows carry `restated: bool`.', self.spec_prompts[0])
        self.assertIn('changed specification docs (review them): docs/contracts.md', t['result'])
        self.assertIn('contract_edit', [r['kind'] for r in self.env.db.q('SELECT kind FROM events WHERE task_id=?', (tid,))])

    def test_verdict_without_the_task_as_written_never_passes(self):
        only_first = lambda lane, cwd, prompt, extra: Result(True, '', dict(spec_verdict([]), exact=True), [lane.model])
        self.env = Env(self.tmp, {'triage': self.tri(), 'work': write_done, 'spec': only_first}, FakeCLM('bounded'))
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run(40)
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'BLOCKED')
        self.assertIn('judged criteria [1], expected 1..2', t['result'])

    def test_contract_doc_pattern(self):
        from aa.quality import CONTRACT_DOC
        for path in ('docs/contracts.md', 'specs/billing/rows.md', 'docs/openapi.yaml', 'api-spec.md',
                     'docs/API.md', 'docs/interface_v2.md', 'contracts/x.json', 'docs/requirements.md'):
            self.assertTrue(CONTRACT_DOC.search(path), path)
        for path in ('requirements.txt', 'dev-requirements.txt', 'notes/inspection.md', 'README.md',
                     'docs/handoff.md', 'docs/capital.md', 'docs/rapid.md'):
            self.assertFalse(CONTRACT_DOC.search(path), path)

    def test_moved_contract_is_an_edit(self):
        self.spec_prompts = []
        def move(lane, cwd, prompt, extra):
            sh(cwd, 'git', 'mv', 'docs/contracts.md', 'docs/old-notes.md')
            return write_done(lane, cwd, prompt, extra)
        tid = self._contract_env(move)
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['data']['contract_edits'], ['docs/contracts.md'])

    def test_new_docs_and_handoff_notes_are_not_contract_edits(self):
        self.spec_prompts = []
        def edit(lane, cwd, prompt, extra):
            (cwd / 'docs' / 'handoff.md').write_text('notes\nchanged X\n')
            (cwd / 'docs' / 'new-api-spec.md').write_text('new\n')
            return write_done(lane, cwd, prompt, extra)
        tid = self._contract_env(edit)
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['data']['contract_edits'], [])
        self.assertNotIn('ORIGINAL text', self.spec_prompts[0])
        self.assertNotIn('changed specification docs', t['result'])


class SimpleDefaultTests(unittest.TestCase):
    """D024 (2026-09-28): the simple pipeline is the default; the full pipeline's stages are opt-in."""

    def test_defaults_are_the_measured_simple_pipeline(self):
        cfg = config.load(Path('/nonexistent'))
        for section in ('oracle_tests', 'best_of_2', 'spec_check', 'failure_triage'):
            self.assertFalse(cfg[section]['enabled'], section)
        self.assertTrue(cfg['workers']['codex_no_memories'])

    def test_simple_flow_delivers_without_judge_oracle_or_race(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls = []
            def work(lane, cwd, prompt, extra):
                calls.append(lane.name); return write_done(lane, cwd, prompt, extra)
            def forbidden(lane, cwd, prompt, extra):
                raise AssertionError('full-pipeline stage called')
            env = Env(Path(tmp), {'triage': triage('bounded', testable=True), 'work': work, 'spec': forbidden,
                                  'oracle': forbidden, 'pick': forbidden}, FakeCLM('bounded'),
                      triage=False, spec=False)
            try:
                tid = env.app.tasks.create(env.target, 'feature')
                env.run()
                t = env.db.task(tid)
                self.assertEqual(t['status'], 'DONE')
                self.assertEqual(calls, ['luna_high'])
            finally:
                env.close()


class LocalFirstTests(unittest.TestCase):
    """Round B (2026-09-28): local Gemma via Codex first; an independent review accepts or escalates."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.lanes, self.judges, self.work_prompts = [], [], []

    def tearDown(self):
        if hasattr(self, 'env'):
            self.env.close()
        self._tmp.cleanup()

    def make(self, work, verdict=lambda n: spec_verdict([])):
        def worker(lane, cwd, prompt, extra):
            self.lanes.append(lane.name); self.work_prompts.append(prompt)
            return work(lane, cwd, prompt, extra)
        def spec(lane, cwd, prompt, extra):
            self.judges.append(lane.name)
            return Result(True, '', verdict(len(self.judges)), [lane.model])
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': worker, 'spec': spec},
                       FakeCLM('bounded'), triage=False, spec=False)
        self.env.cfg.data['local_first']['enabled'] = True
        return self.env.app.tasks.create(self.env.target, 'feature')

    def test_off_by_default(self):
        self.assertFalse(config.load(Path('/nonexistent'))['local_first']['enabled'])

    def test_review_accepts_local_work(self):
        tid = self.make(write_done)
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertEqual(self.lanes, ['gemma_codex'])
        self.assertEqual(self.judges, ['luna_high'])          # reviewed although spec_check is off
        self.assertTrue(t['data']['local_first']['accepted'])

    def test_review_findings_escalate_to_the_tier_lane(self):
        tid = self.make(write_done, verdict=lambda n: spec_verdict(['rows keep restated']))
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertEqual(self.lanes, ['gemma_codex', 'luna_high'])
        self.assertEqual(self.judges, ['luna_high'])          # the paid lane follows the simple pipeline
        self.assertIn('independent review found', self.work_prompts[1])
        self.assertIn('rows keep restated', self.work_prompts[1])
        self.assertEqual(t['data']['local_first']['escalated'], 'review')

    def test_failing_checks_escalate_after_the_lane_budget(self):
        def work(lane, cwd, prompt, extra):
            if lane.name == 'gemma_codex':
                (cwd / 'wrong.txt').write_text(str(len(self.lanes)))     # a real (wrong) change each time
                return Result(True, 'tried', None, [lane.model])
            return write_done(lane, cwd, prompt, extra)
        tid = self.make(work)
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        self.assertEqual(self.lanes, ['gemma_codex', 'gemma_codex', 'luna_high'])
        self.assertEqual(self.judges, [])

    def test_empty_turn_gets_one_free_nudge(self):
        def work(lane, cwd, prompt, extra):
            if len(self.lanes) == 1:
                return Result(True, "I'll start by exploring the code.", None, [lane.model])
            return write_done(lane, cwd, prompt, extra)
        tid = self.make(work)
        self.env.run()
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertEqual(self.lanes, ['gemma_codex', 'gemma_codex'])
        self.assertIn('ended without changing any file', self.work_prompts[1])
        self.assertEqual(t['passes'], 1)                     # the nudge is free

    def test_plain_text_early_stop_is_nudged_even_though_the_schema_failed(self):
        def work(lane, cwd, prompt, extra):
            if len(self.lanes) == 1:     # what _codex returns for a one-sentence plain-text turn
                return Result(False, "I'll start by exploring the code.", None, [], error='no JSON')
            return write_done(lane, cwd, prompt, extra)
        tid = self.make(work)
        self.env.run()
        self.assertEqual(self.lanes, ['gemma_codex', 'gemma_codex'])
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')

    def test_second_empty_turn_is_a_normal_failed_pass(self):
        def work(lane, cwd, prompt, extra):
            if lane.name == 'gemma_codex':
                return Result(True, 'nothing done', None, [lane.model])
            return write_done(lane, cwd, prompt, extra)
        tid = self.make(work)
        self.env.run()
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        self.assertEqual(self.lanes, ['gemma_codex'] * 3 + ['luna_high'])   # nudge free, then 2 passes
        self.assertEqual(self.env.db.task(tid)['data']['local_first']['passes'], 2)

    def test_delivery_note_does_not_claim_a_review_of_escalated_work(self):
        tid = self.make(write_done, verdict=lambda n: spec_verdict(['rows keep restated']))
        self.env.run()
        t = self.env.db.task(tid)
        msg = sh(self.env.target, 'git', 'log', '-1', '--format=%B', t['branch'] or f'aa/{tid}')
        self.assertIn('Spec review: skipped', msg)
        self.assertIn('Local first attempt not accepted (review); the delivered work is by luna_high.', msg)

    def test_race_tiers_skip_local_first(self):
        self.env = Env(self.tmp, {'triage': triage('medium_tough'), 'work': write_done}, FakeCLM('medium_tough'),
                       triage=False, spec=False, best_of_2=True)
        self.env.cfg.data['local_first']['enabled'] = True
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        t = self.env.db.task(tid)
        self.assertNotIn('local_first', t['data'])
        self.assertNotIn('gemma_codex', t['data'].get('lanes_tried', []))

    def test_local_lane_gets_the_schema_in_the_prompt_not_as_a_forced_format(self):
        final = 'Done. Example: {"a": 1}\n{"status": "done", "summary": "ok", "open_items": []}'
        def run(cmd, input, **kw):
            out = Path(cmd[cmd.index('-o') + 1]); out.write_text(final)
            run.cmd, run.input = cmd, input
            return subprocess.CompletedProcess(cmd, 0, '', '')
        with tempfile.TemporaryDirectory() as tmp:
            w = Workers(config.load(Path('/nonexistent'), {'paths': {'state_dir': tmp}}), runner=run)
            res = w.execute(LANES['gemma_codex'], 'task', Path(tmp), schema={'type': 'object'})
        self.assertNotIn('--output-schema', run.cmd)        # vLLM would force JSON on every turn: no tool calls
        self.assertIn('end your final message with one JSON object', run.input)
        self.assertTrue(res.ok)
        self.assertEqual(res.structured, {'status': 'done', 'summary': 'ok', 'open_items': []})

    def test_local_worker_url_must_be_loopback(self):
        from aa.workers import loopback_url
        self.assertEqual(loopback_url('http://127.0.0.1:8100/v1'), 'http://127.0.0.1:8100/v1')
        for bad in ('https://api.example.com/v1', 'http://127.0.0.1.evil.test/v1', 'file:///etc/passwd'):
            with self.assertRaises(ValueError):
                loopback_url(bad)
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        with tempfile.TemporaryDirectory() as tmp:
            cfg = config.load(Path('/nonexistent'), {'paths': {'state_dir': tmp},
                                                     'local_worker': {'base_url': 'http://evil.test/v1", x="1'}})
            w = Workers(cfg, runner=runner)
            with self.assertRaises(ValueError):
                w.execute(LANES['gemma_codex'], 'p', Path(tmp))
        runner.assert_not_called()

    def test_local_codex_command_uses_the_loopback_provider_without_billing_check(self):
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, '', ''))
        with tempfile.TemporaryDirectory() as tmp:
            w = Workers(config.load(Path('/nonexistent'), {'paths': {'state_dir': tmp}}), runner=runner)
            w.verify_billing = mock.Mock(side_effect=AssertionError('no subscription check for the local lane'))
            w.execute(LANES['gemma_codex'], 'p', Path(tmp))
        cmd = ' '.join(runner.call_args[0][0])
        self.assertIn('model_provider="aa_local"', cmd)
        self.assertIn('base_url="http://127.0.0.1:8100/v1"', cmd)
        self.assertIn('gemma-4-31b', cmd)
        self.assertIn('memories.use_memories=false', cmd)
        self.assertIn('requires_openai_auth=false', cmd)


class ConfidenceCheckTests(unittest.TestCase):
    """Round F (2026-09-29): a read-only confidence check after the checks; low -> Fable rework; still low -> deep."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.lanes, self.prompts, self.conf_prompts = [], {}, []

    def tearDown(self):
        if hasattr(self, 'env'):
            self.env.close()
        self._tmp.cleanup()

    def events(self, tid):
        return [(r['kind'], json.loads(r['detail'])) for r in
                self.env.db.q('SELECT kind, detail FROM events WHERE task_id=? ORDER BY id', (tid,))]

    def run_task(self, probs, confidence=True):
        probs = list(probs)

        def work(lane, cwd, prompt, extra):
            self.lanes.append(lane.name); self.prompts[lane.name] = prompt
            (cwd / 'done.txt').write_text(lane.name)
            return Result(True, 'done', None, [lane.model])

        def conf(lane, cwd, prompt, extra):
            self.conf_prompts.append((lane.name, prompt))
            return Result(True, '', {'ambiguities': ['quotes too?'], 'unverified': ['render_link'],
                                     'probability': probs.pop(0)}, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': work, 'conf': conf}, FakeCLM('bounded'),
                       triage=False, spec=False, tier_lanes=None, confidence=confidence)
        tid = self.env.app.tasks.create(self.env.target, 'fix the escaping')
        self.env.run(60)
        return tid, self.env.db.task(tid)

    def test_off_by_default(self):
        self.assertFalse(config.load(Path('/nonexistent'))['confidence_check']['enabled'])
        tid, t = self.run_task([], confidence=False)
        self.assertEqual((t['status'], self.lanes, self.conf_prompts), ('DONE', ['opus_high'], []))

    def test_confident_change_is_delivered(self):
        tid, t = self.run_task([0.9])
        self.assertEqual((t['status'], t['lane'], self.lanes), ('DONE', 'opus_high', ['opus_high']))
        lane, prompt = self.conf_prompts[0]
        self.assertEqual(lane, 'opus_medium')
        self.assertIn('fix the escaping', prompt)
        self.assertIn('done.txt', prompt)                        # the committed diff is shown
        self.assertIn('unstated ones', prompt)                   # the tested checklist wording
        msg = sh(self.env.target_origin, 'git', 'log', '-1', '--format=%B', f'aa/{tid}')
        self.assertIn('Confidence check: 90% by opus_medium', msg)

    def test_low_confidence_hands_the_worktree_to_fable(self):
        tid, t = self.run_task([0.3, 0.85])
        self.assertEqual((t['status'], t['lane']), ('DONE', 'fable_high'))
        self.assertEqual(self.lanes, ['opus_high', 'fable_high'])
        self.assertIn('30%', self.prompts['fable_high'])
        self.assertIn('render_link', self.prompts['fable_high'])  # the check's points reach the rework
        self.assertIn(('escalate', {'frm': 'opus_high', 'to': 'fable_high', 'reason': 'confidence'}), self.events(tid))
        self.assertEqual([c['probability'] for c in t['data']['confidence_checks']], [0.3, 0.85])

    def test_still_low_after_the_rework_goes_to_a_deep_case(self):
        tid, t = self.run_task([0.3, 0.4])
        self.assertEqual(t['status'], 'DEEP')
        self.assertEqual(self.lanes, ['opus_high', 'fable_high'])
        self.assertIn('confidence check 0.40 below 0.75 after 1 rework(s)', t['result'])

    def test_a_broken_check_answer_is_not_a_pass(self):
        def work(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text('x'); return Result(True, 'done', None, [lane.model])
        bad = lambda lane, cwd, prompt, extra: Result(True, '', {'ambiguities': [], 'unverified': [], 'probability': True},
                                                       [lane.model])
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': work, 'conf': bad}, FakeCLM('bounded'),
                       triage=False, spec=False, tier_lanes=None, confidence=True)
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(60)
        self.assertNotEqual(self.env.db.task(tid)['status'], 'DONE')


class LabUsageTests(unittest.TestCase):
    def test_usage_is_counted_by_the_lanes_cli(self):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from tools.lab import usage_totals
        calls = [{'lane': 'luna_high', 'usage': {'input_tokens': 10, 'output_tokens': 5, 'cached_input_tokens': 3}},
                 {'lane': 'opus_medium', 'usage': {'api_equivalent_usd': 0.5}},
                 {'lane': 'fable_high', 'usage': {'api_equivalent_usd': 1.25}},
                 {'lane': 'gemma_codex', 'usage': {'total_tokens': 7, 'input_tokens': 99}}]
        self.assertEqual(usage_totals(calls), {'codex_tokens': 15, 'codex_cached': 3, 'claude_usd_equiv': 1.75,
                                               'local_tokens': 7})


class WorkerAssumptionsTests(unittest.TestCase):
    """ask-r1 (2026-10-01): the builder's guesses where the request was silent reach the owner."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        if hasattr(self, 'env'):
            self.env.close()
        self._tmp.cleanup()

    def run_with(self, assumptions):
        def work(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text('ok')
            return Result(True, 'done', {'status': 'done', 'summary': 'implemented', 'open_items': [], 'question': '',
                                         'rebuttals': [], 'spec_conflicts': [], 'assumptions': assumptions}, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': work}, FakeCLM('bounded'), triage=False,
                       spec=False, tier_lanes=None)
        tid = self.env.app.tasks.create(self.env.target, 'implement transfer')
        self.env.run(60)
        return tid

    def test_schema_and_prompt_ask_for_assumptions(self):
        from aa.tasks import WORKER_SCHEMA
        self.assertIn('assumptions', WORKER_SCHEMA['required'])
        self.assertIn('assumptions:', (Path(__file__).resolve().parents[1] / 'aa/prompts/worker.md').read_text())

    def test_assumptions_reach_the_delivery_note_and_the_owner(self):
        tid = self.run_with(['A repeated idempotency key returns True, like a fresh transfer.'])
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        msg = sh(self.env.target_origin, 'git', 'log', '-1', '--format=%B', f'aa/{tid}')
        self.assertIn('Assumptions (check these):\n- A repeated idempotency key returns True', msg)
        done = [m for title, m, kw in self.env.sent if title.startswith('Done')]
        self.assertTrue(done and 'A repeated idempotency key returns True' in done[-1])

    def test_no_assumptions_no_section(self):
        tid = self.run_with([])
        msg = sh(self.env.target_origin, 'git', 'log', '-1', '--format=%B', f'aa/{tid}')
        self.assertNotIn('Assumptions', msg)


class ResearchPhaseTests(unittest.TestCase):
    """Owner, 2026-10-02: a new project gets a research offer first; the brief reaches the owner and the builder."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.prompts = []

    def tearDown(self):
        if hasattr(self, 'env'):
            self.env.close()
        self._tmp.cleanup()

    def make(self, research=True):
        def work(lane, cwd, prompt, extra):
            self.prompts.append(prompt); (cwd / 'done.txt').write_text('ok')
            return Result(True, 'done', None, [lane.model])

        def research_fn(lane, cwd, prompt, extra):
            self.research_prompt = prompt
            return Result(True, '', {'brief': '## Summary\nUse the token bucket design (Smith 2025).',
                                     'sources': [{'title': 'Token buckets', 'url': 'https://example.org/tb', 'supports': 'design'}],
                                     'open_questions': ['Per-user or global limits?']}, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': work, 'research': research_fn}, FakeCLM('bounded'),
                       triage=False, spec=False, tier_lanes=None, research=research)
        return self.env.app.tasks.create(self.env.target, 'build a rate limiter service')

    def test_new_project_gets_one_offer_with_buttons(self):
        tid = self.make()
        self.env.run(5)
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'WAIT_OWNER')
        title, msg, kw = self.env.sent[-1]
        self.assertIn('research first', title.lower())
        self.assertIn(('Research first', f'research {tid}'), kw['choices'])
        self.assertIn(('Skip', f'noresearch {tid}'), kw['choices'])

    def test_research_brief_reaches_owner_and_builder(self):
        tid = self.make()
        self.env.run(5)
        self.env.db.inbox_put(f'research {tid}')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertEqual(t['status'], 'DONE')
        self.assertIn('build a rate limiter service', self.research_prompt)
        self.assertTrue(any(n.endswith('-research') for n in self.env.workers.web_calls))   # the web is allowed there only
        self.assertTrue(any('token bucket' in m for title, m, kw in self.env.sent if title.startswith('Research brief')))
        self.assertIn('token bucket design', self.prompts[0])                  # context for the builder
        self.assertIn('request above stays authoritative', self.prompts[0])
        self.assertTrue(Path(t['data']['research']['file']).read_text().count('https://example.org/tb'))

    def test_skip_goes_straight_on_and_is_not_offered_again(self):
        tid = self.make()
        self.env.run(5)
        self.env.db.inbox_put(f'noresearch {tid}')
        self.env.run(60)
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        self.assertNotIn('research brief', ' '.join(self.prompts).lower())
        tid2 = self.env.app.tasks.create(self.env.target, 'second task in the same young repo')
        self.env.run(60)
        self.assertEqual(self.env.db.task(tid2)['status'], 'DONE')              # once per repository

    def test_established_repo_gets_no_offer(self):
        def work(lane, cwd, prompt, extra):
            (cwd / 'done.txt').write_text('ok'); return Result(True, 'done', None, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': work}, FakeCLM('bounded'), triage=False, spec=False,
                       tier_lanes=None, research=True)
        for i in range(5):                                   # an established project: history and files
            for j in range(4):
                (self.env.target / f'mod_{i}_{j}.py').write_text(f'x = {i}{j}\n')
            sh(self.env.target, 'git', 'add', '-A')
            sh(self.env.target, 'git', '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', f'c{i}')
        tid = self.env.app.tasks.create(self.env.target, 'small fix')
        self.env.run(60)
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        self.assertFalse(any('research' in title.lower() for title, m, kw in self.env.sent))

    def test_established_repo_and_switch_off_are_not_offered(self):
        tid = self.make(research=False)
        self.env.run(60)
        self.assertEqual(self.env.db.task(tid)['status'], 'DONE')
        self.assertFalse(any('research' in title.lower() for title, m, kw in self.env.sent))


class TierLaneTests(unittest.TestCase):
    """Round C (2026-09-28): routine/bounded worker lanes are configurable (Opus vs Luna)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.lanes = []

    def tearDown(self):
        if hasattr(self, 'env'):
            self.env.close()
        self._tmp.cleanup()

    def events(self, tid):
        return [(r['kind'], json.loads(r['detail'])) for r in
                self.env.db.q('SELECT kind, detail FROM events WHERE task_id=? ORDER BY id', (tid,))]

    def run_tier(self, tier, lanes=None):
        def work(lane, cwd, prompt, extra):
            self.lanes.append(lane.name); return write_done(lane, cwd, prompt, extra)
        self.env = Env(self.tmp, {'triage': triage(tier), 'work': work}, FakeCLM(tier), triage=False, spec=False,
                       tier_lanes=None)
        if lanes:
            self.env.cfg.data['tier_lanes'].update(lanes)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run()
        return self.env.db.task(tid)

    def test_defaults_are_opus_high(self):
        self.assertEqual(config.load(Path('/nonexistent'))['tier_lanes'], {'routine': 'opus_high', 'bounded': 'opus_high'})
        self.assertEqual(self.run_tier('routine')['status'], 'DONE')
        self.assertEqual(self.lanes, ['opus_high'])

    def test_failed_opus_passes_escalate_to_astra(self):
        def work(lane, cwd, prompt, extra):
            self.lanes.append(lane.name)
            if lane.name == 'astra_high':
                (cwd / 'done.txt').write_text('ok')
            return Result(True, 'done', None, [lane.model])
        self.env = Env(self.tmp, {'triage': triage('bounded'), 'work': work}, FakeCLM('bounded'), triage=False,
                       spec=False, tier_lanes=None)
        tid = self.env.app.tasks.create(self.env.target, 'feature')
        self.env.run(60)
        t = self.env.db.task(tid)
        self.assertEqual((t['status'], t['lane']), ('DONE', 'astra_high'))
        self.assertEqual(self.lanes, ['opus_high', 'opus_high', 'astra_high'])
        self.assertIn(('escalate', {'frm': 'opus_high', 'to': 'astra_high'}), self.events(tid))

    def test_bounded_and_routine_can_go_to_opus(self):
        t = self.run_tier('routine', {'routine': 'opus_medium', 'bounded': 'opus_medium'})
        self.assertEqual(t['status'], 'DONE')
        self.assertEqual(self.lanes, ['opus_medium'])

    def test_unknown_lane_is_an_error(self):
        from aa.tasks import TaskFlow
        flow = TaskFlow.__new__(TaskFlow)
        flow.cfg = config.load(Path('/nonexistent'), {'tier_lanes': {'bounded': 'gpt_whatever'}})
        with self.assertRaises(ValueError):
            flow._tier_lane('bounded')


class ClaudeRefreshRaceTests(unittest.TestCase):
    """round-c-r1: parallel Claude Code processes raced to refresh the shared login; the losers failed."""

    def test_refresh_race_is_retried_not_counted_as_a_failed_pass(self):
        race = json.dumps({'is_error': True, 'result': 'Failed to refresh OAuth token: another Claude Code '
                           'process is refreshing it or exited mid-refresh.'})
        ok = json.dumps({'is_error': False, 'result': 'done', 'modelUsage': {'claude-opus-5-5': {}}})
        outs = [race, race, ok]
        runner = mock.Mock(side_effect=lambda *a, **k: subprocess.CompletedProcess([], 0, outs.pop(0), ''))
        with tempfile.TemporaryDirectory() as tmp:
            w = Workers(config.load(Path('/nonexistent'), {'paths': {'state_dir': tmp},
                                                           'workers': {'claude_refresh_wait_s': 0}}), runner=runner)
            w.verify_billing = lambda cli: None
            res = w.execute(LANES['opus_medium'], 'p', Path(tmp))
        self.assertTrue(res.ok)
        self.assertEqual(runner.call_count, 3)

    def test_persistent_refresh_failure_still_fails_after_the_retries(self):
        race = json.dumps({'is_error': True, 'result': 'Failed to refresh OAuth token: another Claude Code process'})
        runner = mock.Mock(return_value=subprocess.CompletedProcess([], 0, race, ''))
        with tempfile.TemporaryDirectory() as tmp:
            w = Workers(config.load(Path('/nonexistent'), {'paths': {'state_dir': tmp},
                                                           'workers': {'claude_refresh_wait_s': 0}}), runner=runner)
            w.verify_billing = lambda cli: None
            res = w.execute(LANES['opus_medium'], 'p', Path(tmp))
        self.assertFalse(res.ok)
        self.assertEqual(runner.call_count, 4)
