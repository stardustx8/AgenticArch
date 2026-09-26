"""Quality multipliers baked into the task flow: oracle tests, mutation gate, best-of-2.

Triggers (config `oracle_tests`, `best_of_2`), evaluated by the coordinator, never by a model:
- Oracle tests: tier in oracle_tests.tiers AND triage says the task is testable AND the repo has
  checks. A model from the OTHER vendor than the implementer writes acceptance tests before any
  implementation; they must fail on the base commit or they are discarded. They become a required
  check and are read-only for workers (edits are reverted and logged as tampering).
- Mutation gate: after all checks pass, simple mutants of the changed source lines must be killed
  by the oracle tests; a low score is reported to the spec judge (tests may be weak).
- Best-of-2: tier in best_of_2.tiers, or a Luna task exhausted its retries (on_escalation). Astra
  and Opus implement in parallel worktrees against the same oracle tests; checks decide first,
  a pairwise judge only when both pass. The winner continues through the normal pipeline.
Evidence: eval/PROBES.md research notes (independent tests beat in-loop tests; cross-vendor
candidate pools raise the chance that a correct fix exists; selection is the bottleneck).
"""
from __future__ import annotations

import random
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import checks as checks_mod
from . import git
from .decisions import PEER_LANES
from .workers import LANES, BillingError

ORACLE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['test_files', 'command', 'notes'],
    'properties': {'test_files': {'type': 'array', 'items': {'type': 'string'}},
                   'command': {'type': 'string'}, 'notes': {'type': 'string'}},
}
PICK_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['winner', 'reason'],
    'properties': {'winner': {'type': 'string', 'enum': ['A', 'B']}, 'reason': {'type': 'string'}},
}
SOURCE_EXT = ('.py', '.js', '.ts', '.tsx', '.jsx', '.go', '.rs', '.java', '.kt', '.rb', '.php', '.cs')
MUTATIONS = [  # (pattern, replacement) applied to one occurrence on one added line
    (r'==', '!='), (r'!=', '=='), (r'<=', '<'), (r'>=', '>'), (r'(?<![<>=!])<(?![<=])', '<='),
    (r'(?<![<>=!-])>(?![>=])', '>='), (r'(?<![+\-])\+(?![+=])', '-'), (r'(?<![+\-])-(?![-=>])', '+'),
    (r'(?<!\*)\*(?![*=])', '/'), (r'\bTrue\b', 'False'), (r'\bFalse\b', 'True'), (r'\btrue\b', 'false'),
    (r'\bfalse\b', 'true'), (r'\band\b', 'or'), (r'\bor\b', 'and'), (r'&&', '||'), (r'\|\|', '&&'),
    (r'\b(\d+)\b', lambda m: str(int(m.group(1)) + 1)),
]


def other_vendor(lane: str) -> str:
    return 'opus_medium' if LANES[lane].cli == 'codex' else 'astra_high'


class QualityMixin:
    """Mixed into TaskFlow; uses its cfg, db, workers, n, render helpers."""

    # ------------------------------------------------------------ triggers
    def _plan_quality(self, t: dict, lane: str | None) -> None:
        """Called by routing once the tier is known: oracle first, then race or single lane."""
        tri = t['data'].get('triage') or {}
        race = (self.cfg['best_of_2'].get('enabled', True) and
                t['tier'] in self.cfg['best_of_2'].get('tiers', ['medium_tough']))
        t['data']['mode'] = 'race' if race else 'single'
        t['data']['planned_lane'] = lane
        oc = self.cfg['oracle_tests']
        if (oc.get('enabled', True) and not t['data'].get('oracle_tried') and t['tier'] in oc.get('tiers', [])
                and tri.get('testable') and t['data'].get('checks')):
            self.db.update_task(t['id'], data=t['data'], status='ORACLE')
            return
        self._start_after_oracle(t)

    def _start_after_oracle(self, t: dict) -> None:
        if t['data'].get('mode') == 'race':
            self.db.update_task(t['id'], data=t['data'], status='RACE')
        else:
            self._start_lane(t, t['data'].get('planned_lane'))

    def _start_commit(self, t: dict) -> str:
        return (t['data'].get('oracle') or {}).get('commit') or t['base_ref']

    # --------------------------------------------------------- oracle tests
    def _oracle(self, t: dict) -> None:
        t['data']['oracle_tried'] = True
        repo = Path(t['repo'])
        wt = self.cfg.worktrees / f'{t["id"]}-oracle'
        git.add_worktree(repo, wt, f'aa/{t["id"]}-oracle', t['base_ref'])
        author = (self.cfg['oracle_tests'].get('author_for_race', 'luna_high') if t['data'].get('mode') == 'race'
                  else other_vendor(t['data'].get('planned_lane') or 'luna_high'))
        tri = t['data'].get('triage') or {}
        from .tasks import bullet, render
        prompt = render('oracle.md', worktree=wt, prompt=t['prompt'],
                        acceptance=bullet(tri.get('acceptance_criteria')),
                        checks=bullet([f'{k}: `{v}`' for k, v in (t['data'].get('checks') or {}).items()], '- (none)'),
                        owner_answers=self._answers_text(t))
        try:
            res = self.workers.execute(LANES[author], prompt, wt, schema=ORACLE_SCHEMA, log_name=f'{t["id"]}-oracle')
        except BillingError as exc:
            res = None
            self.db.event('oracle_skipped', t['id'], reason=f'billing: {exc}'[:300])
        verdict = self._validate_oracle(t, wt, res)
        if verdict:
            t['data']['oracle'] = verdict
            t['data']['checks'] = {**t['data'].get('checks', {}), 'oracle_tests': verdict['command']}
            self.db.event('oracle_ready', t['id'], author=author, files=verdict['files'][:10])
        else:
            git.remove_worktree(repo, wt)
            git.git(repo, 'branch', '-D', f'aa/{t["id"]}-oracle', check=False)
        self.db.update_task(t['id'], data=t['data'])
        self._start_after_oracle(self.db.task(t['id']))

    def _validate_oracle(self, t: dict, wt: Path, res) -> dict | None:
        if res is None or not res.ok or not res.structured or not res.structured.get('command', '').strip():
            self.db.event('oracle_rejected', t['id'], reason='author failed or gave no command')
            return None
        changed = git.changed_paths(wt)
        tests = [p for p in changed if _is_test_path(p)]
        others = [p for p in changed if not _is_test_path(p)]
        for p in others:                          # the oracle author may only add tests
            git.git(wt, 'checkout', '--', p, check=False)
            git.git(wt, 'clean', '-qf', '--', p, check=False)
        if not tests:
            self.db.event('oracle_rejected', t['id'], reason='no test files written')
            return None
        cmd = res.structured['command'].strip()
        base_run = checks_mod.run({'oracle': cmd}, wt, timeout=900)[0]
        if base_run.ok:                           # tests pass without the feature: they test nothing new
            self.db.event('oracle_rejected', t['id'], reason='tests already pass on the base commit')
            return None
        commit = git.commit_all(wt, f'aa {t["id"]}: independent acceptance tests (oracle)')
        return {'files': tests, 'command': cmd, 'commit': commit, 'base_failure': base_run.output[-800:]}

    def _protect_oracle(self, t: dict, wt: Path) -> list[str]:
        """Restore oracle test files after a worker run; return the ones the worker had changed."""
        oracle = t['data'].get('oracle')
        if not oracle:
            return []
        touched = [f for f in oracle['files'] if _differs(wt, oracle['commit'], f)]
        if touched:
            git.git(wt, 'checkout', oracle['commit'], '--', *touched, check=False)
            self.db.event('oracle_tamper', t['id'], files=touched)
            t['data'].setdefault('oracle_tampered', []).extend(touched)
        return touched

    # -------------------------------------------------------- mutation gate
    def _mutation_gate(self, t: dict, wt: Path) -> None:
        oracle = t['data'].get('oracle')
        if not oracle or t['data'].get('mutation'):
            return
        start = oracle['commit']
        files = [f for f in git.git(wt, 'diff', '--name-only', f'{start}..HEAD', check=False).splitlines()
                 if f.endswith(SOURCE_EXT) and not _is_test_path(f) and f not in oracle['files']]
        mutants = []
        for f in files:
            for ln in _added_lines(wt, start, f):
                for pat, rep in MUTATIONS:
                    text = (wt / f).read_text().splitlines(keepends=True)[ln - 1]
                    if re.search(pat, text) and not text.lstrip().startswith(('#', '//', 'import', 'from ')):
                        mutants.append((f, ln, pat, rep))
                        break
        rng = random.Random(t['id'])
        rng.shuffle(mutants)
        mutants = mutants[:int(self.cfg['oracle_tests'].get('max_mutants', 12))]
        killed, survivors = 0, []
        for f, ln, pat, rep in mutants:
            path = wt / f
            original = path.read_text()
            lines = original.splitlines(keepends=True)
            lines[ln - 1] = re.sub(pat, rep, lines[ln - 1], count=1)
            path.write_text(''.join(lines))
            try:
                r = checks_mod.run({'oracle': oracle['command']}, wt, timeout=300)[0]
            finally:
                path.write_text(original)
            if r.ok:
                survivors.append(f'{f}:{ln}: {lines[ln - 1].strip()[:120]}')
            else:
                killed += 1
        git.discard(wt)
        score = killed / len(mutants) if mutants else None
        t['data']['mutation'] = {'score': score, 'killed': killed, 'total': len(mutants), 'survivors': survivors[:6]}
        self.db.event('mutation_gate', t['id'], score=score, killed=killed, total=len(mutants))
        self.db.update_task(t['id'], data=t['data'])

    def _quality_note_for_judge(self, t: dict) -> str:
        notes = []
        m = t['data'].get('mutation') or {}
        if m.get('score') is not None and m['score'] < float(self.cfg['oracle_tests'].get('min_mutation_score', 0.5)):
            notes.append(f'The independent acceptance tests are weak: they detected only {m["killed"]} of '
                         f'{m["total"]} deliberately planted bugs in the changed code; surviving mutants:\n' +
                         '\n'.join(f'  - {s}' for s in m['survivors']) +
                         '\nJudge the criteria from the code itself, not from the passing tests.')
        if t['data'].get('oracle_tampered'):
            notes.append('The worker modified the independent acceptance tests (the changes were reverted): '
                         + ', '.join(sorted(set(t['data']['oracle_tampered']))) + '. Treat this as tampering.')
        return ('\n' + '\n'.join(notes) + '\n') if notes else ''

    # ------------------------------------------------------------ best-of-2
    def _race(self, t: dict) -> None:
        repo = Path(t['repo'])
        start = self._start_commit(t)
        old = self.cfg.worktrees / t['id']
        if old.exists():                                         # escalation: drop the failed attempt
            git.remove_worktree(repo, old)
            git.git(repo, 'branch', '-D', f'aa/{t["id"]}', check=False)
        lanes = list(PEER_LANES.values())                        # astra_high, opus_high
        tri = t['data'].get('triage') or {}
        from .tasks import WORKER_SCHEMA, render, worker_report, bullet
        cands = {}
        for lane in lanes:
            wt = self.cfg.worktrees / f'{t["id"]}-{lane}'
            git.add_worktree(repo, wt, f'aa/{t["id"]}-{lane}', start)
            cands[lane] = wt
        prompt_for = lambda wt: render(
            'worker.md', worktree=wt, branch=f'aa/{t["id"]}', prompt=t['prompt'],
            acceptance=bullet(tri.get('acceptance_criteria')),
            paths=', '.join(tri.get('relevant_paths') or []) or '(explore as needed)',
            checks=bullet([f'{k}: `{v}`' for k, v in (t['data'].get('checks') or {}).items()], '- (none configured)'),
            previous=self._oracle_worker_note(t) + (
                f'\nAn earlier attempt by another model failed; its feedback:\n{t["data"]["last_failure"]}\n'
                if t['data'].get('last_failure') else ''),
            owner_answers=self._answers_text(t))

        def run(lane):
            try:
                return lane, self.workers.execute(LANES[lane], prompt_for(cands[lane]), cands[lane],
                                                  schema=WORKER_SCHEMA, log_name=f'{t["id"]}-race-{lane}')
            except BillingError as exc:
                return lane, exc
        with ThreadPoolExecutor(2) as pool:
            outcomes = dict(pool.map(run, lanes))
        results = {}
        for lane, res in outcomes.items():
            wt = cands[lane]
            if isinstance(res, BillingError):
                results[lane] = {'status': 'error', 'failed': 99, 'summary': str(res)}
                continue
            rep = worker_report(res)
            self._protect_oracle(t, wt)
            git.commit_all(wt, f'aa wip {t["id"]} race ({lane})')
            failed = 99
            if rep['status'] == 'done' and (res.ok or rep['from_schema']):
                runs = checks_mod.run(t['data'].get('checks') or {}, wt)
                git.discard(wt)
                failed = sum(1 for r in runs if not r.ok)
            results[lane] = {'status': rep['status'], 'failed': failed, 'summary': rep['summary'][-600:],
                             'question': rep['question'], 'seconds': round(res.seconds)}
        t['data']['race'] = results
        t['data'].setdefault('lanes_tried', []).extend(l for l in lanes if l not in t['data']['lanes_tried'])
        if all(r['status'] == 'blocked' for r in results.values()):
            self._cleanup_race(t, keep=None)
            self._ask_owner(t, next(iter(results.values()))['question'] or 'The workers need your input.')
            return
        passing = [l for l, r in results.items() if r['failed'] == 0 and r['status'] == 'done']
        if len(passing) == 2:
            winner, reason, did = self._pairwise_pick(t, cands, lanes)
        elif len(passing) == 1:
            winner, reason, did = passing[0], 'only candidate passing all checks', None
        else:
            winner = min(lanes, key=lambda l: (results[l]['failed'], l != PEER_LANES.get(tri.get('peer'), '')))
            reason, did = 'no candidate passed; fewest failing checks', None
        if did is None:
            did = self.db.decision('best_of_2', t['id'], t['prompt'][:4000], {'A': lanes[0], 'B': lanes[1]},
                                   None, None, winner)
        t['data']['race_winner'] = {'lane': winner, 'reason': reason, 'decision_id': did}
        self.db.event('race_winner', t['id'], lane=winner, reason=reason[:300],
                      failed={l: r['failed'] for l, r in results.items()})
        self._cleanup_race(t, keep=winner)
        wt = self.cfg.worktrees / t['id']
        git.git(repo, 'worktree', 'move', str(cands[winner]), str(wt))
        git.git(wt, 'branch', '-m', f'aa/{t["id"]}')
        self.db.update_task(t['id'], lane=winner, lane_passes=1, passes=t['passes'] + 1, worktree=str(wt),
                            branch=f'aa/{t["id"]}', data=t['data'], status='VERIFY')

    def _pairwise_pick(self, t: dict, cands: dict, lanes: list[str]):
        order = lanes[:]
        random.Random(t['id']).shuffle(order)                   # position-bias control, reproducible
        start = self._start_commit(t)
        diff = lambda l: git.git(cands[l], 'diff', f'{start}..HEAD', check=False)[:30000]
        from .tasks import bullet, render
        prompt = render('pick.md', prompt=t['prompt'],
                        acceptance=bullet((t['data'].get('triage') or {}).get('acceptance_criteria')),
                        diff_a=diff(order[0]), diff_b=diff(order[1]))
        # Judges prefer their own family's output, so both vendors judge; agreement wins,
        # disagreement falls back to a deterministic tie-break (research notes in eval/PROBES.md).
        votes = {}
        for judge in self.cfg['best_of_2'].get('judge_lanes', ['opus_medium', 'astra_high']):
            try:
                res = self.workers.execute(LANES[judge], prompt, cands[order[0]], write=False,
                                           schema=PICK_SCHEMA, log_name=f'{t["id"]}-pick-{judge}')
            except BillingError:
                continue
            if res.ok and res.structured:
                votes[judge] = (order[0] if res.structured['winner'] == 'A' else order[1],
                                res.structured['reason'][:200])
        picks = {v[0] for v in votes.values()}
        if len(votes) >= 2 and len(picks) == 1:
            winner = picks.pop()
            reason = 'judges agree: ' + ' | '.join(f'{j}: {v[1]}' for j, v in votes.items())
        else:
            sizes = {l: len(diff(l)) for l in lanes}
            winner = min(lanes, key=sizes.get)
            reason = (f'judges split ({", ".join(f"{j}->{v[0]}" for j, v in votes.items()) or "none"}); '
                      'tie-break: smaller diff')
        t['data']['pick_votes'] = {j: v[0] for j, v in votes.items()}
        did = self.db.decision('best_of_2', t['id'], t['prompt'][:4000], {'A': order[0], 'B': order[1]},
                               None, winner, winner)
        return winner, reason, did

    def _cleanup_race(self, t: dict, keep: str | None) -> None:
        repo = Path(t['repo'])
        for lane in PEER_LANES.values():
            if lane == keep:
                continue
            git.remove_worktree(repo, self.cfg.worktrees / f'{t["id"]}-{lane}')
            git.git(repo, 'branch', '-D', f'aa/{t["id"]}-{lane}', check=False)

    def _oracle_worker_note(self, t: dict) -> str:
        oracle = t['data'].get('oracle')
        if not oracle:
            return ''
        return (f'\nIndependent acceptance tests were written before you started: {", ".join(oracle["files"])} '
                f'(run with `{oracle["command"]}`). They must pass. They are read-only: any change to them is '
                'reverted and reported as tampering. If you believe a test is wrong, say so in `rebuttals`.\n')


def _is_test_path(p: str) -> bool:
    name = p.rsplit('/', 1)[-1].lower()
    return (bool(re.search(r'(^|/)(tests?|__tests__|spec|specs)(/|$)', p.lower())) or name.startswith('test_') or
            re.search(r'(_test|\.test|\.spec|_spec)\.[a-z]+$', name) is not None)


def _differs(wt: Path, commit: str, f: str) -> bool:
    cur = wt / f
    ref = git.git(wt, 'show', f'{commit}:{f}', check=False, strip=False)
    return not cur.exists() or cur.read_text() != ref


def _added_lines(wt: Path, start: str, f: str) -> list[int]:
    out = git.git(wt, 'diff', '-U0', f'{start}..HEAD', '--', f, check=False)
    lines = []
    for m in re.finditer(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', out, re.M):
        start_ln, count = int(m.group(1)), int(m.group(2) or 1)
        lines.extend(range(start_ln, start_ln + count))
    return lines


def cleanup_quality_worktrees(cfg, t: dict) -> None:
    repo = Path(t['repo'])
    git.remove_worktree(repo, cfg.worktrees / f'{t["id"]}-oracle')
    git.git(repo, 'branch', '-D', f'aa/{t["id"]}-oracle', check=False)
