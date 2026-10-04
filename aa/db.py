"""SQLite state: tasks, deep cases, events, CLM decisions, confirmed repo checks."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  repo TEXT NOT NULL,             -- absolute path of the target git checkout
  base_ref TEXT,                  -- commit the work starts from
  prompt TEXT NOT NULL,
  status TEXT NOT NULL,           -- see tasks.STATUSES
  tier TEXT,                      -- routine|bounded|medium_tough|tough
  tier_source TEXT,               -- owner|agree|codex|clm|owner_pick
  lane TEXT,                      -- worker lane (luna_low ... opus_high)
  passes INTEGER NOT NULL DEFAULT 0,
  lane_passes INTEGER NOT NULL DEFAULT 0,
  case_id TEXT,
  branch TEXT,
  worktree TEXT,
  data TEXT NOT NULL DEFAULT '{}', -- JSON: triage output, checks, failures
  busy INTEGER NOT NULL DEFAULT 0, -- a step is executing in the daemon
  result TEXT
);
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY,
  task_id TEXT NOT NULL,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  phase TEXT NOT NULL,            -- see cases.PHASES
  pro_turn INTEGER NOT NULL DEFAULT 0,   -- number of Pro turns requested so far
  pro_reviews INTEGER NOT NULL DEFAULT 0,
  round INTEGER NOT NULL DEFAULT 0,      -- challenge round within the current cycle
  cycle INTEGER NOT NULL DEFAULT 0,
  branch TEXT NOT NULL,
  data TEXT NOT NULL DEFAULT '{}',
  busy INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  task_id TEXT,
  case_id TEXT,
  kind TEXT NOT NULL,
  detail TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  task_id TEXT,
  kind TEXT NOT NULL,             -- tier|peer|context
  state TEXT NOT NULL,
  options TEXT NOT NULL,          -- JSON {id: description}
  clm TEXT,                       -- JSON probabilities or null when unavailable
  proposed TEXT,                  -- CLM argmax
  final TEXT,                     -- what was actually used
  outcome TEXT                    -- filled later: pass|fail|escalated ...
);
CREATE TABLE IF NOT EXISTS repo_checks (
  repo TEXT PRIMARY KEY,
  checks TEXT NOT NULL,           -- JSON {name: command}
  confirmed INTEGER NOT NULL DEFAULT 0,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS inbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  line TEXT NOT NULL,             -- owner reply, same grammar as ntfy replies
  done INTEGER NOT NULL DEFAULT 0
);
"""


def new_id(prefix: str) -> str:
    return f'{prefix}{time.strftime("%m%d")}-{uuid.uuid4().hex[:5]}'


class DB:
    def __init__(self, path: Path | str):
        if str(path) != ':memory:':
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path), timeout=30, isolation_level=None,
                                    check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.conn.execute('PRAGMA journal_mode=WAL')
        self.conn.execute('PRAGMA busy_timeout=30000')
        self.conn.executescript(SCHEMA)

    # -- generic ---------------------------------------------------------
    def q(self, sql: str, args: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, tuple(args)).fetchall()

    def x(self, sql: str, args: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.lock:
            return self.conn.execute(sql, tuple(args))

    # -- owner inbox (CLI replies) --------------------------------------
    def inbox_put(self, line: str) -> None:
        self.x('INSERT INTO inbox(ts, line) VALUES (?,?)', (time.time(), line.strip()))

    def inbox_take(self) -> list[str]:
        with self.lock:
            rows = self.q('SELECT id, line FROM inbox WHERE done=0 ORDER BY id')
            for r in rows:
                self.x('UPDATE inbox SET done=1 WHERE id=?', (r['id'],))
        return [r['line'] for r in rows]

    def event(self, kind: str, task_id: str | None = None, case_id: str | None = None,
              **detail: Any) -> None:
        self.x('INSERT INTO events(ts, task_id, case_id, kind, detail) VALUES (?,?,?,?,?)',
               (time.time(), task_id, case_id, kind, json.dumps(detail, default=str)))

    def kv_get(self, k: str, default: str | None = None) -> str | None:
        r = self.q('SELECT v FROM kv WHERE k=?', (k,))
        return r[0]['v'] if r else default

    def kv_set(self, k: str, v: str) -> None:
        self.x('INSERT INTO kv(k, v) VALUES (?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v', (k, v))

    # -- tasks -------------------------------------------------------------
    def create_task(self, repo: str, prompt: str, tier: str | None = None) -> str:
        tid = new_id('t')
        now = time.time()
        self.x('INSERT INTO tasks(id, created, updated, repo, prompt, status, tier, tier_source) '
               'VALUES (?,?,?,?,?,?,?,?)',
               (tid, now, now, repo, prompt, 'NEW', tier, 'owner' if tier else None))
        self.event('task_created', tid, repo=repo, tier=tier)
        return tid

    def task(self, tid: str) -> dict | None:
        r = self.q('SELECT * FROM tasks WHERE id=?', (tid,))
        return _row(r[0]) if r else None

    def update_task(self, tid: str, **fields: Any) -> None:
        _update(self, 'tasks', tid, fields)

    def tasks(self, statuses: Iterable[str] | None = None) -> list[dict]:
        if statuses is None:
            return [_row(r) for r in self.q('SELECT * FROM tasks ORDER BY created')]
        st = list(statuses)
        marks = ','.join('?' * len(st))
        return [_row(r) for r in self.q(f'SELECT * FROM tasks WHERE status IN ({marks}) ORDER BY created', st)]

    # -- cases -------------------------------------------------------------
    def create_case(self, task_id: str) -> str:
        cid = new_id('c')
        now = time.time()
        self.x('INSERT INTO cases(id, task_id, created, updated, phase, branch) VALUES (?,?,?,?,?,?)',
               (cid, task_id, now, now, 'NEW', f'case/{cid}'))
        self.event('case_created', task_id, cid)
        return cid

    def case(self, cid: str) -> dict | None:
        r = self.q('SELECT * FROM cases WHERE id=?', (cid,))
        return _row(r[0]) if r else None

    def update_case(self, cid: str, **fields: Any) -> None:
        _update(self, 'cases', cid, fields)

    def cases(self, phases: Iterable[str] | None = None) -> list[dict]:
        if phases is None:
            return [_row(r) for r in self.q('SELECT * FROM cases ORDER BY created')]
        ph = list(phases)
        marks = ','.join('?' * len(ph))
        return [_row(r) for r in self.q(f'SELECT * FROM cases WHERE phase IN ({marks}) ORDER BY created', ph)]

    # -- decisions ---------------------------------------------------------
    def decision(self, kind: str, task_id: str | None, state: str, options: dict,
                 clm: dict | None, proposed: str | None, final: str | None) -> int:
        cur = self.x('INSERT INTO decisions(ts, task_id, kind, state, options, clm, proposed, final) '
                     'VALUES (?,?,?,?,?,?,?,?)',
                     (time.time(), task_id, kind, state, json.dumps(options),
                      json.dumps(clm) if clm is not None else None, proposed, final))
        return int(cur.lastrowid)

    def decision_outcome(self, task_id: str, kind: str, outcome: str) -> None:
        self.x('UPDATE decisions SET outcome=? WHERE task_id=? AND kind=? AND outcome IS NULL',
               (outcome, task_id, kind))

    def decision_final(self, did: int, final: str) -> None:
        self.x('UPDATE decisions SET final=? WHERE id=?', (final, did))

    # -- repo checks -------------------------------------------------------
    def repo_checks(self, repo: str) -> dict | None:
        r = self.q('SELECT * FROM repo_checks WHERE repo=?', (repo,))
        if not r:
            return None
        return {'checks': json.loads(r[0]['checks']), 'confirmed': bool(r[0]['confirmed'])}

    def set_repo_checks(self, repo: str, checks: dict, confirmed: bool) -> None:
        self.x('INSERT INTO repo_checks(repo, checks, confirmed, updated) VALUES (?,?,?,?) '
               'ON CONFLICT(repo) DO UPDATE SET checks=excluded.checks, confirmed=excluded.confirmed, '
               'updated=excluded.updated', (repo, json.dumps(checks), int(confirmed), time.time()))


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    if 'data' in d:
        d['data'] = json.loads(d['data'] or '{}')
    return d


def _update(db: DB, table: str, rid: str, fields: dict) -> None:
    if not fields:
        return
    fields = dict(fields)
    if 'data' in fields and not isinstance(fields['data'], str):
        fields['data'] = json.dumps(fields['data'], default=str)
    fields['updated'] = time.time()
    cols = ', '.join(f'{k}=?' for k in fields)
    db.x(f'UPDATE {table} SET {cols} WHERE id=?', (*fields.values(), rid))
