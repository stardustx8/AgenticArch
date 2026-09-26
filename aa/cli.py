"""`aa` command line.

  aa task [--repo DIR] [--tier TIER] "what to do"   queue a task (daemon picks it up)
  aa status [-a]                                    active tasks/cases (-a: all)
  aa show ID                                        details, recent events
  aa prompt CASE                                    the current one-line Pro prompt
  aa answer "tier <task> <tier>" | "checks <task> ok|none" | "answer <case|task> <text>"
            | "resume <case>" | "cancel <id>" | "retry <task>" | "accept <task>" | "code <task>"
  aa doctor                                         verify subscriptions, CLM, ntfy, git
  aa daemon                                         run the coordinator (systemd does this)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

from . import config as config_mod
from .db import DB


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog='aa', description='AgenticArch coordinator')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('task')
    p.add_argument('prompt', nargs='+')
    p.add_argument('--repo', default='.')
    p.add_argument('--tier', choices=['routine', 'bounded', 'medium_tough', 'tough'])
    p = sub.add_parser('status')
    p.add_argument('-a', '--all', action='store_true')
    sub.add_parser('show').add_argument('id')
    sub.add_parser('prompt').add_argument('case')
    sub.add_parser('answer').add_argument('line', nargs='+')
    sub.add_parser('doctor')
    sub.add_parser('daemon')
    a = ap.parse_args(argv)
    cfg = config_mod.load()

    if a.cmd == 'daemon':
        from .daemon import App
        App(cfg).serve()
        return 0
    if a.cmd == 'doctor':
        return doctor(cfg)

    db = DB(cfg.db_path)
    if a.cmd == 'task':
        from . import git
        from .tasks import TIERS
        repo = Path(a.repo).expanduser().resolve()
        tid = db.create_task(str(git.toplevel(repo)), ' '.join(a.prompt), a.tier)
        db.update_task(tid, base_ref=git.head(repo))
        assert a.tier is None or a.tier in TIERS
        print(tid)
        return 0
    if a.cmd == 'answer':
        db.inbox_put(' '.join(a.line))
        print('queued for the daemon')
        return 0
    if a.cmd == 'status':
        rows = db.tasks() if a.all else db.tasks(('NEW', 'TRIAGED', 'READY', 'VERIFY', 'SPEC', 'DELIVER',
                                                  'WAIT_OWNER', 'DEEP', 'BLOCKED'))
        if not rows:
            print('no active tasks' if not a.all else 'no tasks')
        for t in rows:
            extra = ''
            if t['case_id']:
                c = db.case(t['case_id'])
                extra = f' case {c["id"]}:{c["phase"]} pro#{c["pro_turn"]} cycle{c["cycle"]}/r{c["round"]}'
            age = int((time.time() - t['created']) / 60)
            print(f'{t["id"]}  {t["status"]:<10} {t["tier"] or "?":<12} {t["lane"] or "-":<11}'
                  f' {age:>4}m  {Path(t["repo"]).name}: {t["prompt"][:50]!r}{extra}')
        return 0
    if a.cmd == 'show':
        item = db.task(a.id) or db.case(a.id)
        if not item:
            print('unknown id', file=sys.stderr)
            return 1
        print(json.dumps(item, indent=2, default=str))
        col = 'task_id' if a.id.startswith('t') else 'case_id'
        for e in db.q(f'SELECT * FROM events WHERE {col}=? ORDER BY id DESC LIMIT 15', (a.id,))[::-1]:
            print(time.strftime('%H:%M:%S', time.localtime(e['ts'])), e['kind'], e['detail'][:300])
        return 0
    if a.cmd == 'prompt':
        c = db.case(a.case)
        print(c['data'].get('pro_prompt', '(no Pro turn requested yet)') if c else 'unknown case')
        return 0
    return 1


def doctor(cfg) -> int:
    from .clm import CLM
    from .workers import BillingError, Workers
    db = DB(cfg.db_path)
    ok = True

    def line(name: str, good: bool, detail: str = '') -> None:
        nonlocal ok
        ok &= good
        print(f'{"OK  " if good else "FAIL"} {name}{": " + detail if detail else ""}')

    w = Workers(cfg)
    for cli in ('codex', 'claude'):
        try:
            w.verify_billing(cli)
            line(f'{cli} subscription login', True)
        except BillingError as exc:
            line(f'{cli} subscription login', False, str(exc))
    if cfg['decider']['backend'] == 'semif':
        from .semif import SemIf
        line('SemIf decider', SemIf(cfg, db).available(), cfg['semif']['socket'])
    clm = CLM(cfg, db)
    if cfg['decider']['backend'] == 'clm':
        line('CLM server', clm.available(), cfg['clm']['url'])
    if cfg['decider']['backend'] == 'clm' and clm.available():
        try:
            line('CLM tokenizer', clm.count_tokens('hello world') > 0)
            line('CLM deployment digest', len(clm.deployment_digest()) == 64)
        except Exception as exc:
            line('CLM tokenizer/digest', False, repr(exc))
    try:
        urllib.request.urlopen(cfg['ntfy']['url'] + '/v1/health', timeout=5).read()
        line('ntfy', True, cfg['ntfy']['url'])
    except OSError as exc:
        line('ntfy', False, str(exc))
    from . import git
    try:
        git.git(Path.home(), 'ls-remote', cfg['case_repo']['url'], timeout=30)
        line('case repo access', True, cfg['case_repo']['slug'])
    except git.GitError as exc:
        line('case repo access', False, str(exc)[:200])
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
