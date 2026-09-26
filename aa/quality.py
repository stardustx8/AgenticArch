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
PY_OPS = {'==': '!=', '!=': '==', '<': '<=', '<=': '<', '>': '>=', '>=': '>', '+': '-', '-': '+', '*': '/',
          '//': '*', '%': '*', 'and': 'or', 'or': 'and', 'True': 'False', 'False': 'True', 'is': 'is not'}
MUTATIONS = [  # (pattern, replacement) for non-Python code; one per line, outside strings/comments
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
        accepted = []
        for author in self._oracle_authors(t):
            v = self._author_oracle(t, wt, author)
            if v:
                accepted.append((author, v))
                self.db.event('oracle_ready', t['id'], author=author, files=v['files'][:10])
        if accepted:
            t['data']['oracle'] = {'files': [f for _, v in accepted for f in v['files']],
                                   'command': ' && '.join(f'( {v["command"]} )' for _, v in accepted),
                                   'commit': accepted[-1][1]['commit'], 'authors': [a for a, _ in accepted]}
            t['data']['checks'] = {**t['data'].get('checks', {}), 'oracle_tests': t['data']['oracle']['command']}
        else:
            git.remove_worktree(repo, wt)
            git.git(repo, 'branch', '-D', f'aa/{t["id"]}-oracle', check=False)
        self.db.update_task(t['id'], data=t['data'])
        self._start_after_oracle(self.db.task(t['id']))

    def _local_ok(self, lane: str) -> bool:
        return LANES[lane].cli != 'local' or self.workers.local_available()

    def _oracle_authors(self, t: dict) -> list[str]:
        """Race: a neutral third family writes the tests. Single lane: the other vendor, plus the
        local model as an additional independent test set."""
        oc = self.cfg['oracle_tests']
        if t['data'].get('mode') == 'race':
            a = oc.get('author_for_race', 'luna_high')
            return [a if self._local_ok(a) else 'luna_high']
        authors = [other_vendor(t['data'].get('planned_lane') or 'luna_high')]
        extra = oc.get('extra_author')
        if extra and extra not in authors and self._local_ok(extra):
            authors.append(extra)
        return authors

    def _author_oracle(self, t: dict, wt: Path, author: str) -> dict | None:
        from .tasks import bullet, render
        tri = t['data'].get('triage') or {}
        local = LANES[author].cli == 'local'
        if local:
            prompt = render('oracle_local.md', prompt=t['prompt'], acceptance=bullet(tri.get('acceptance_criteria')),
                            context=_repo_context(wt, tri.get('relevant_paths') or []),
                            owner_answers=self._answers_text(t))
        else:
            prompt = render('oracle.md', worktree=wt, prompt=t['prompt'],
                            acceptance=bullet(tri.get('acceptance_criteria')),
                            checks=bullet([f'{k}: `{v}`' for k, v in (t['data'].get('checks') or {}).items()], '- (none)'),
                            owner_answers=self._answers_text(t))
        verdict, problem = None, ''
        for attempt in (1, 2):                      # one repair round with the exact validation error
            repair = (f'\nYour previous tests were rejected: {problem}\nFix them.\n' if problem else '')
            try:
                res = self.workers.execute(LANES[author], prompt + repair, wt,
                                           schema=LOCAL_ORACLE_SCHEMA if local else ORACLE_SCHEMA,
                                           log_name=f'{t["id"]}-{author}' + ('' if attempt == 1 else '-repair') + '-oracle')
            except BillingError as exc:
                self.db.event('oracle_skipped', t['id'], author=author, reason=f'billing: {exc}'[:300])
                break
            if local and res.ok and res.structured:
                _write_local_tests(wt, res.structured.get('files') or [])
            verdict, problem = self._validate_oracle(t, wt, res)
            if verdict or not problem.startswith('invalid'):
                break
            git.discard(wt)                        # start the repair from the last accepted state
        if not verdict:
            git.discard(wt)
        return verdict

    def _validate_oracle(self, t: dict, wt: Path, res) -> tuple[dict | None, str]:
        """Returns (oracle, '') or (None, reason). Reasons starting with 'invalid' allow one repair."""
        def reject(reason: str):
            self.db.event('oracle_rejected', t['id'], reason=reason[:300])
            return None, reason
        if res is None or not res.ok or not res.structured or not res.structured.get('command', '').strip():
            return reject('author failed or gave no command')
        changed = git.changed_paths(wt)
        tests = [p for p in changed if _is_test_path(p)]
        for p in (p for p in changed if not _is_test_path(p)):      # the oracle author may only add tests
            git.git(wt, 'checkout', '--', p, check=False)
            git.git(wt, 'clean', '-qf', '--', p, check=False)
        if not tests:
            return reject('no test files written')
        for f in tests:                                            # the tests themselves must be valid code
            err = _syntax_error(wt, f)
            if err:
                return reject(f'invalid test file {f}: {err}')
        cmd = res.structured['command'].strip()
        base_run = checks_mod.run({'oracle': cmd}, wt, timeout=900)[0]
        if base_run.ok:                           # tests pass without the feature: they test nothing new
            return reject('tests already pass on the base commit')
        if SYNTAX_RE.search(base_run.output):
            return reject('invalid: the tests fail with a syntax/parse error, not because the feature is missing: '
                          + base_run.output[-600:])
        commit = git.commit_all(wt, f'aa {t["id"]}: independent acceptance tests (oracle)')
        return {'files': tests, 'command': cmd, 'commit': commit, 'base_failure': base_run.output[-800:]}, ''

    def _drop_oracle(self, t: dict, reason: str) -> None:
        """Safety net: an oracle that only blocks and is disputed by the implementer is removed."""
        if not t['data'].get('oracle'):
            return
        t['data']['checks'].pop('oracle_tests', None)
        t['data']['oracle_dropped'] = reason[:500]
        t['data']['oracle'] = None
        self.db.event('oracle_dropped', t['id'], reason=reason[:300])

    def _oracle_disputed(self, t: dict, texts: list[str]) -> bool:
        oracle = t['data'].get('oracle') or {}
        names = [f.rsplit('/', 1)[-1] for f in oracle.get('files', [])]
        blob = ' '.join(texts).lower()
        return any(n.lower() in blob for n in names) or 'acceptance test' in blob

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
            mutants.extend((f, *m) for m in _mutants_for(wt / f, set(_added_lines(wt, start, f))))
        rng = random.Random(t['id'])
        rng.shuffle(mutants)
        mutants = mutants[:int(self.cfg['oracle_tests'].get('max_mutants', 12))]
        killed, survivors = 0, []
        for f, ln, col, end, rep in mutants:
            path = wt / f
            original = path.read_text()
            lines = original.splitlines(keepends=True)
            line = lines[ln - 1]
            lines[ln - 1] = line[:col] + rep + line[end:]
            path.write_text(''.join(lines))
            try:
                r = checks_mod.run({'oracle': oracle['command']}, wt, timeout=300)[0]
            finally:
                path.write_text(original)
            if r.ok:
                survivors.append(f'{f}:{ln}: `{line[col:end]}` -> `{rep}` in: {line.strip()[:100]}')
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
            notes.append(f'The independent acceptance tests may be weak: they detected only {m["killed"]} of '
                         f'{m["total"]} deliberately planted bugs in the changed code. Surviving mutants (some may be '
                         'equivalent, i.e. not change behaviour; check which ones would):\n' +
                         '\n'.join(f'  - {s}' for s in m['survivors']) +
                         '\nJudge the criteria from the code itself, not from the passing tests.')
        if t['data'].get('oracle_dropped'):
            notes.append('The independent acceptance tests were dropped as invalid (' + t['data']['oracle_dropped'][:300] +
                         '). Verify the criteria from the code itself.')
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
        if t['data'].get('race_results_saved') and all(w.exists() for w in cands.values()):
            results = t['data']['race']                       # resume after a crash: no second race
            return self._select(t, cands, lanes, results)
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
            failed, failing = 99, []
            if rep['status'] in ('done', 'partial') and (res.ok or rep['from_schema']):
                runs = checks_mod.run(t['data'].get('checks') or {}, wt)
                git.discard(wt)
                failing = [r.name for r in runs if not r.ok]
                failed = len(failing)
            results[lane] = {'status': rep['status'], 'failed': failed, 'failing': failing,
                             'summary': rep['summary'][-600:], 'rebuttals': rep['rebuttals'][:5],
                             'question': rep['question'], 'seconds': round(res.seconds)}
        t['data']['race'] = results
        t['data']['race_results_saved'] = True
        t['data'].setdefault('lanes_tried', []).extend(l for l in lanes if l not in t['data']['lanes_tried'])
        self.db.update_task(t['id'], data=t['data'])
        self._select(t, cands, lanes, results)

    def _select(self, t: dict, cands: dict, lanes: list[str], results: dict) -> None:
        repo = Path(t['repo'])
        tri = t['data'].get('triage') or {}
        if all(r['status'] == 'blocked' for r in results.values()):
            self._cleanup_race(t, keep=None)
            self._ask_owner(t, next(iter(results.values()))['question'] or 'The workers need your input.')
            return
        passing = [l for l, r in results.items() if r['failed'] == 0 and r['status'] == 'done']
        oracle_only = [l for l, r in results.items() if r['failing'] == ['oracle_tests']]
        if not passing and oracle_only and self._oracle_disputed(
                t, [results[l]['summary'] + ' '.join(results[l]['rebuttals']) for l in oracle_only]):
            self._drop_oracle(t, 'every candidate passed all other checks and disputed the acceptance tests: ' +
                              results[oracle_only[0]]['summary'][:300])
            passing = oracle_only
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
            except Exception as exc:              # a judge problem must never re-run the race
                self.db.event('pick_judge_error', t['id'], judge=judge, error=repr(exc)[:300])
                continue
            if res.ok and res.structured:
                votes[judge] = (order[0] if res.structured['winner'] == 'A' else order[1],
                                res.structured['reason'][:200])
        picks = {v[0] for v in votes.values()}
        tb = self.cfg['best_of_2'].get('tiebreak_lane')
        tb_picks = []
        if not (len(votes) >= 2 and len(picks) == 1) and tb and self._local_ok(tb):
            for o in (order, order[::-1]):              # both orders: only a consistent answer counts
                p = render('pick.md', prompt=t['prompt'],
                           acceptance=bullet((t['data'].get('triage') or {}).get('acceptance_criteria')),
                           diff_a=diff(o[0]), diff_b=diff(o[1]))
                try:
                    r = self.workers.execute(LANES[tb], p, cands[o[0]], write=False, schema=PICK_SCHEMA,
                                             log_name=f'{t["id"]}-pick-tiebreak')
                except Exception as exc:
                    self.db.event('pick_judge_error', t['id'], judge=tb, error=repr(exc)[:300])
                    break
                if r.ok and r.structured:
                    tb_picks.append(o[0] if r.structured['winner'] == 'A' else o[1])
            t['data']['tiebreak_votes'] = tb_picks
        if len(votes) >= 2 and len(picks) == 1:
            winner = picks.pop()
            reason = 'judges agree: ' + ' | '.join(f'{j}: {v[1]}' for j, v in votes.items())
        elif len(tb_picks) == 2 and tb_picks[0] == tb_picks[1]:
            winner = tb_picks[0]
            reason = (f'judges split ({", ".join(f"{j}->{v[0]}" for j, v in votes.items())}); '
                      f'tie-break by {tb}, consistent in both orders')
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


SYNTAX_RE = re.compile(r'SyntaxError|IndentationError|TabError|ParseError|Unexpected token|'
                       r'syntax error|expected .* found|error\[E0\d+\]: expected')


def _syntax_error(wt: Path, f: str) -> str:
    """Cheap language-aware syntax check of a test file ('' = fine or unknown language)."""
    import shutil
    import subprocess
    path = wt / f
    if f.endswith('.py'):
        cmd = ['python3', '-c', 'import ast,sys\ntry: ast.parse(open(sys.argv[1]).read(), sys.argv[1])\n'
               'except SyntaxError as e: print(f"SyntaxError: {e.msg} (line {e.lineno})"); sys.exit(1)', str(path)]
    elif f.endswith(('.js', '.mjs', '.cjs')) and shutil.which('node'):
        cmd = ['node', '--check', str(path)]
    else:
        return ''
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return '' if p.returncode == 0 else (p.stderr or p.stdout).strip()[-400:]


def _mutants_for(path: Path, added: set[int]) -> list[tuple[int, int, int, str]]:
    """Mutants (line, col, end_col, replacement) on added lines, only in real code (not strings/comments)."""
    if not added or not path.exists():
        return []
    out: list[tuple[int, int, int, str]] = []
    if path.suffix == '.py':
        import io
        import tokenize
        seen = set()
        try:
            toks = list(tokenize.generate_tokens(io.StringIO(path.read_text()).readline))
        except (tokenize.TokenError, SyntaxError, IndentationError):
            return []
        for tok in toks:
            ln = tok.start[0]
            if ln not in added or ln in seen or tok.start[0] != tok.end[0]:
                continue
            rep = None
            if tok.type == tokenize.OP or (tok.type == tokenize.NAME and tok.string in PY_OPS):
                rep = PY_OPS.get(tok.string)
            elif tok.type == tokenize.NUMBER and tok.string.isdigit():
                rep = str(int(tok.string) + 1)
            if rep is not None:
                out.append((ln, tok.start[1], tok.end[1], rep))
                seen.add(ln)                      # one mutant per line keeps runs bounded
        return out
    lines = path.read_text().splitlines()
    for ln in sorted(added):
        if ln > len(lines):
            continue
        text = lines[ln - 1]
        if text.lstrip().startswith(('//', '#', '*', '/*', 'import ', 'from ')):
            continue
        for pat, rep in MUTATIONS:
            for m in re.finditer(pat, text):
                prefix = text[:m.start()]
                if prefix.count('"') % 2 or prefix.count("'") % 2 or prefix.count('`') % 2 or '//' in prefix:
                    continue                      # inside a string literal or after a comment marker
                out.append((ln, m.start(), m.end(), rep(m) if callable(rep) else rep))
                break
            else:
                continue
            break
    return out


LOCAL_ORACLE_SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['files', 'command', 'notes'],
    'properties': {
        'files': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['path', 'content'],
            'properties': {'path': {'type': 'string'}, 'content': {'type': 'string'}}}},
        'command': {'type': 'string'}, 'notes': {'type': 'string'}},
}


def _write_local_tests(wt: Path, files: list[dict]) -> None:
    """Write model-proposed test files: new files only, inside the worktree, test paths only."""
    root = wt.resolve()
    for f in files[:6]:
        rel = str(f.get('path', '')).strip().lstrip('/')
        target = (wt / rel).resolve()
        if (not rel or '..' in Path(rel).parts or not str(target).startswith(str(root) + '/') or
                target.exists() or not _is_test_path(rel)):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(str(f.get('content', '')))


def _repo_context(wt: Path, relevant: list[str], budget: int = 24000) -> str:
    """Relevant source files plus one existing test file as a convention example."""
    parts, used = [], 0
    tracked = git.git(wt, 'ls-files', check=False).splitlines()
    example = next((p for p in tracked if _is_test_path(p) and p.endswith(SOURCE_EXT)), None)
    for p in [*relevant[:6], *([example] if example else [])]:
        path = wt / p
        if not p or not path.is_file() or p in [x[0] for x in parts]:
            continue
        text = path.read_text(errors='replace')[:6000]
        if used + len(text) > budget:
            break
        used += len(text)
        parts.append((p, text))
    listing = '\n'.join(tracked[:200])
    return (f'All tracked files:\n{listing}\n\n' +
            '\n\n'.join(f'--- {p}{" (example test)" if p == example else ""}\n{text}' for p, text in parts))
