#!/usr/bin/env python3
"""Harness lab: run the real aa pipeline on lab tasks under a named variant and score it.

Each run: fresh git repo from eval/lab/tasks/<id>/repo, isolated state dir, config overrides from
the variant, simulated owner (every simulated answer counts as a ping), then the HIDDEN tests are
run on the delivered branch. Results: eval/lab/results/<variant>.jsonl (one line per task).

  python3 tools/lab.py --variant baseline --flags '{}' [--tasks 'b1_*,b5_*'] [--parallel 3]
  python3 tools/lab.py --report                       # compare all variants (paired on tasks)
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
LAB = ROOT / 'eval' / 'lab'
RESULTS = LAB / 'results'
TERMINAL = ('DONE', 'FAILED', 'BLOCKED', 'CANCELLED', 'DEEP')
AUTO_ANSWER = ('No further information is available. Choose the most reasonable interpretation of the task, '
               'state your assumptions in the summary, and continue.')


def sh(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class CallLog:
    """Wraps Workers.execute to record every model call (lane, seconds, usage)."""

    def __init__(self, workers):
        self.w, self.calls, self.lock = workers, [], threading.Lock()
        orig = workers.execute

        def execute(lane, prompt, cwd, **kw):
            t0 = time.time()
            res = orig(lane, prompt, cwd, **kw)
            with self.lock:
                self.calls.append({'lane': lane.name, 'kind': kw.get('log_name', '').split('-', 2)[-1],
                                   'seconds': round(time.time() - t0, 1), 'ok': res.ok, 'usage': res.usage})
            return res
        workers.execute = execute


def run_task(task_dir: Path, variant: str, flags: dict, timeout_s: int) -> dict:
    from aa import config
    from aa.daemon import App
    from aa.db import DB
    meta = json.loads((task_dir / 'task.json').read_text())
    with tempfile.TemporaryDirectory(prefix=f'lab-{meta["id"]}-') as tmp:
        tmp = Path(tmp)
        repo = tmp / 'repo'
        shutil.copytree(task_dir / 'repo', repo)
        (repo / '.agenticarch.toml').write_text(
            '[checks]\ntests = "python3 -m unittest discover -s tests -t . -q"\n')
        sh(repo, 'git', 'init', '-q', '-b', 'main')
        sh(repo, 'git', 'add', '-A')
        sh(repo, 'git', '-c', 'user.name=lab', '-c', 'user.email=lab@lab', 'commit', '-qm', 'base')
        overrides = {'paths': {'state_dir': str(tmp / 'state')}, 'ntfy': {'enabled': False},
                     'delivery': {'push_branch': False}}
        for section, values in flags.items():
            overrides.setdefault(section, {}).update(values)
        cfg = config.load(overrides=overrides)
        db = DB(tmp / 'state' / 'aa.sqlite')
        app = App(cfg, db)
        pings = []
        app.n.send = lambda title, msg, **kw: pings.append(title) if kw.get('choices') or 'Question' in title else None
        log = CallLog(app.workers)
        tid = app.tasks.create(repo, meta['prompt'])
        t0 = time.time()
        owner_answers = 0
        answered = None
        while time.time() - t0 < timeout_s:
            app.tick()
            t = db.task(tid)
            if t['status'] in TERMINAL:
                break
            if t['status'] == 'WAIT_OWNER' and answered != t['updated']:   # simulated owner, once per wait
                answered = t['updated']
                owner_answers += 1
                d = t['data']
                if d.get('worker_question'):
                    db.inbox_put(f'answer {tid} {AUTO_ANSWER}')
                elif d.get('spec_wait'):
                    db.inbox_put(f'accept {tid}')
                elif d.get('env_wait'):
                    db.inbox_put(f'code {tid}')
                elif (d.get('tier_votes') or {}).get('codex'):
                    db.inbox_put(f'tier {tid} {d["tier_votes"]["codex"]}')
                else:
                    db.inbox_put(f'checks {tid} ok')
            time.sleep(1)
        t = db.task(tid)
        hidden = hidden_all = None
        art = RESULTS / 'runs' / variant / meta['id']            # evidence kept for failure analysis
        shutil.rmtree(art, ignore_errors=True)
        art.mkdir(parents=True, exist_ok=True)
        (art / 'task.json').write_text(json.dumps({k: v for k, v in t.items() if k != 'data'}, indent=1, default=str))
        (art / 'data.json').write_text(json.dumps(t['data'], indent=1, default=str))
        (art / 'events.txt').write_text('\n'.join(f'{e["kind"]} {e["detail"]}' for e in
                                                  db.q('SELECT kind, detail FROM events ORDER BY id')))
        wt_oracle = tmp / 'state' / 'worktrees' / f'{tid}-oracle'
        if wt_oracle.exists():
            for f in (t['data'].get('oracle') or {}).get('files', []):
                if (wt_oracle / f).exists():
                    (art / f'oracle__{Path(f).name}').write_text((wt_oracle / f).read_text())
        if t['status'] == 'DONE':
            check = tmp / 'check'
            sh(repo, 'git', 'worktree', 'add', '-q', str(check), t['branch'] or f'aa/{tid}')
            shutil.copytree(task_dir / 'hidden', check, dirs_exist_ok=True)
            run = lambda pat: subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-t', '.',
                                              '-p', pat], cwd=check, capture_output=True, text=True, timeout=300)
            h = run('test_hidden_*.py')
            hidden = h.returncode == 0
            hidden_all = run('test*.py').returncode == 0
            (art / 'hidden_output.txt').write_text(h.stdout + h.stderr)
            (art / 'delivered.diff').write_text(sh(repo, 'git', 'diff', 'main', t['branch'] or f'aa/{tid}'))
        d = t['data']
        usage = {'codex_tokens': 0, 'codex_cached': 0, 'claude_usd_equiv': 0.0, 'local_tokens': 0}
        for c in log.calls:
            u = c['usage'] or {}
            if c['lane'].startswith(('luna', 'astra')):
                usage['codex_tokens'] += (u.get('input_tokens', 0) or 0) + (u.get('output_tokens', 0) or 0)
                usage['codex_cached'] += u.get('cached_input_tokens', 0) or 0
            elif c['lane'].startswith('opus'):
                usage['claude_usd_equiv'] += u.get('api_equivalent_usd') or 0
            else:
                usage['local_tokens'] += u.get('total_tokens', 0) or 0
        return {'variant': variant, 'task': meta['id'], 'tier_hint': meta['tier_hint'], 'status': t['status'],
                'tier': t['tier'], 'lane': t['lane'], 'hidden_pass': hidden, 'all_tests_pass': hidden_all,
                'seconds': round(time.time() - t0), 'pings': owner_answers, 'passes': t['passes'],
                'spec_loops': d.get('spec_loops', 0), 'oracle': bool(d.get('oracle')),
                'race': bool(d.get('race')), 'mutation': (d.get('mutation') or {}).get('score'),
                'calls': len(log.calls), 'calls_by_lane': _count(c['lane'] for c in log.calls), **usage,
                'flags': flags, 'ts': time.strftime('%Y-%m-%d %H:%M')}


def _count(items) -> dict:
    out: dict = {}
    for i in items:
        out[i] = out.get(i, 0) + 1
    return out


def mcnemar_p(win: int, loss: int) -> float:
    """Exact two-sided McNemar (binomial) p-value on discordant pairs."""
    from math import comb
    n = win + loss
    if n == 0:
        return 1.0
    k = min(win, loss)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n)


def report(ref: str = 'baseline') -> None:
    rows = [json.loads(l) for f in sorted(RESULTS.glob('*.jsonl')) for l in open(f)]
    by = {}
    for r in rows:
        by.setdefault(r['variant'], {})[r['task']] = r      # latest run per task wins
    base = by.get(ref, {})
    print(f'{"variant":24} {"n":>3} {"hidden pass":>11} {"vs " + ref + " (paired)":>22} {"min":>6} '
          f'{"codex Mtok":>10} {"claude $eq":>10} {"pings":>6}')
    for v, tasks in sorted(by.items()):
        rs = list(tasks.values())
        n = len(rs)
        passed = sum(1 for r in rs if r['hidden_pass'])
        paired = [t for t in tasks if t in base and v != ref]
        win = sum(1 for t in paired if tasks[t]['hidden_pass'] and not base[t]['hidden_pass'])
        loss = sum(1 for t in paired if base[t]['hidden_pass'] and not tasks[t]['hidden_pass'])
        cmp = f'+{win}/-{loss} p={mcnemar_p(win, loss):.2f}' if paired else '-'
        print(f'{v:24} {n:>3} {passed / n:>10.0%} {cmp:>22} {sum(r["seconds"] for r in rs) / 60 / n:>6.1f} '
              f'{sum(r["codex_tokens"] for r in rs) / 1e6 / n:>10.2f} {sum(r["claude_usd_equiv"] for r in rs) / n:>10.2f} '
              f'{sum(r["pings"] for r in rs) / n:>6.2f}')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--variant')
    ap.add_argument('--flags', default='{}')
    ap.add_argument('--tasks', default='*')
    ap.add_argument('--parallel', type=int, default=3)
    ap.add_argument('--timeout', type=int, default=2700)
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--ref', default='baseline', help='variant the report compares against')
    a = ap.parse_args()
    if a.report:
        report(a.ref)
        return 0
    flags = json.loads(a.flags)
    tasks = sorted(d for d in (LAB / 'tasks').iterdir()
                   if any(fnmatch.fnmatch(d.name, p) for p in a.tasks.split(',')))
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / f'{a.variant}.jsonl'
    lock = threading.Lock()

    def one(d):
        try:
            r = run_task(d, a.variant, flags, a.timeout)
        except Exception as exc:                            # a crashed run is a result, not a stop
            r = {'variant': a.variant, 'task': d.name, 'status': 'ERROR', 'error': repr(exc)[:500],
                 'hidden_pass': False, 'seconds': 0, 'pings': 0, 'codex_tokens': 0, 'claude_usd_equiv': 0}
        with lock:
            with open(out, 'a') as fh:
                fh.write(json.dumps(r) + '\n')
            print(f'{r["task"]:32} {r["status"]:9} hidden={r["hidden_pass"]} {r.get("seconds")}s', flush=True)
    with ThreadPoolExecutor(a.parallel) as pool:
        list(pool.map(one, tasks))
    report()
    return 0


if __name__ == '__main__':
    sys.exit(main())
