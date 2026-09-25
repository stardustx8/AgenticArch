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
        fn = self.script[_kind(log_name)]
        return fn(lane, Path(cwd), prompt, extra_dirs)


def _kind(log_name: str) -> str:
    for k in ('-fix', '-opus', '-astra'):
        if k in log_name:
            return k.strip('-')
    return 'work'


def triage(tier, cats=(), peer='astra'):
    return {'tier': tier, 'peer': peer, 'pro_categories': list(cats), 'summary': 's',
            'acceptance_criteria': ['a'], 'relevant_paths': ['app.py'], 'risks': []}


class Env:
    def __init__(self, tmp: Path, script: dict, clm: FakeCLM, checks='test -f done.txt', policy='codex'):
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
            attempts.append((lane.name, 'checks failed' in prompt))
            if len(attempts) == 3:
                (cwd / 'done.txt').write_text('ok')
            return Result(True, 'tried', None, [lane.model])

        self.env = Env(self.tmp, {'triage': triage('routine'), 'work': flaky}, FakeCLM('routine'))
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
                       FakeCLM('medium_tough', peer='astra'))
        tid = self.env.app.tasks.create(self.env.target, 'x')
        self.env.run(60)
        t = self.env.db.task(tid)
        lanes = [c[0] for c in self.env.workers.calls if not c[1].endswith('-triage')]
        self.assertEqual(lanes[:4], ['astra_high', 'astra_high', 'opus_high', 'opus_high'])
        self.assertNotIn('opus_medium', lanes, 'peer choice switches models only, not effort')
        self.assertEqual(t['status'], 'DEEP')

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
        self.assertEqual(self.env.db.task(tid)['status'], 'BLOCKED')

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
        self.assertEqual(cmd[cmd.index('--permission-mode') + 1], 'auto')
        settings = json.loads(cmd[cmd.index('--settings') + 1])['sandbox']
        self.assertTrue(settings['failIfUnavailable'])
        self.assertEqual(settings['filesystem']['allowWrite'], [tmp])
        self.assertIn('~/.ssh', settings['filesystem']['denyRead'])

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
