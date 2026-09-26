"""The `aa` daemon: advances every task and case, handles owner replies.

One process (systemd user service). Steps run in a small thread pool; a
`busy` flag in SQLite prevents running the same task/case twice. On start,
stale busy flags from a crash are cleared and each item resumes from its
stored status.
"""
from __future__ import annotations

import re
import signal
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from . import cases, git, tasks
from .clm import CLM
from .config import Config
from .db import DB
from .notify import Notifier
from .semif import SemIf
from .workers import Workers


def make_decider(cfg: Config, db: DB):
    """Local semantic decider selected by config `decider.backend` (semif | clm)."""
    if cfg['decider']['backend'] == 'clm':
        return CLM(cfg, db)
    return SemIf(cfg, db)


TASK_LOG = re.compile(r'^(t\d{4}-[0-9a-f]{5})(?:-|$)')


class App:
    def __init__(self, cfg: Config, db: DB | None = None, workers: Workers | None = None,
                 decider=None, notifier: Notifier | None = None):
        self.cfg = cfg
        git.IDENTITY.update(cfg['git'])
        self.db = db or DB(cfg.db_path)
        self.n = notifier or Notifier(cfg, self.db)
        self.decider = decider or make_decider(cfg, self.db)
        self.workers = workers or Workers(cfg)
        self._count_model_calls()
        self.tasks = tasks.TaskFlow(cfg, self.db, self.workers, self.decider, self.n)
        self.cases = cases.CaseFlow(cfg, self.db, self.workers, self.decider, self.n)

    def _count_model_calls(self) -> None:
        """Log every model call of a task (log names start with the task id) for the call cap."""
        orig = self.workers.execute

        def execute(lane, prompt, cwd, **kw):
            m = TASK_LOG.match(kw.get('log_name', ''))
            if m:
                self.db.event('model_call', m.group(1), lane=lane.name, job=kw['log_name'][len(m.group(1)) + 1:])
            return orig(lane, prompt, cwd, **kw)
        self.workers.execute = execute

    def _over_call_cap(self, tid: str) -> bool:
        cap = int(self.cfg['retry'].get('max_model_calls', 40))
        n = self.db.q("SELECT COUNT(*) AS n FROM events WHERE task_id=? AND kind='model_call' AND id > "
                      "COALESCE((SELECT MAX(id) FROM events WHERE task_id=? AND kind='call_budget_reset'), 0)",
                      (tid, tid))[0]['n']
        if n < cap:
            return False
        self.db.update_task(tid, status='BLOCKED', result=f'stopped after {n} model calls (retry.max_model_calls)')
        self.db.event('model_call_cap', tid, calls=n)
        self.n.send(f'Blocked {tid}', f'Stopped after {n} model calls - probably a loop. Check the events, '
                    f'then aa answer "retry {tid}" or "cancel {tid}".', tags='warning')
        return True

    # -------------------------------------------------------------- replies
    def handle_reply(self, line: str) -> None:
        parts = line.split(maxsplit=2)
        if len(parts) < 2:
            self.db.event('reply_ignored', line=line)
            return
        verb, ident, rest = parts[0].lower(), parts[1], parts[2] if len(parts) > 2 else ''
        try:
            if verb == 'tier':
                self.tasks.set_tier(ident, rest.strip())
            elif verb == 'checks':
                self.tasks.confirm_checks(ident, rest.strip() or 'ok')
            elif verb == 'answer' and self.db.task(ident):
                self.tasks.answer_worker(ident, rest)
            elif verb == 'answer':
                self.cases.answer(ident, rest)
            elif verb == 'resume':
                self.cases.resume(ident)
            elif verb == 'cancel':
                self.cancel(ident)
            elif verb == 'retry':
                self.retry(ident)
            elif verb == 'accept':
                self.tasks.accept_spec(ident)
            elif verb == 'code':
                self.tasks.env_as_code(ident)
            else:
                self.db.event('reply_ignored', line=line)
                return
            self.db.event('reply', line=line)
        except Exception as exc:
            self.db.event('reply_error', line=line, error=repr(exc))
            self.n.send('Reply not applied', f'{line}\n{exc}', tags='warning')

    def cancel(self, ident: str) -> None:
        if self.db.task(ident):
            self.db.update_task(ident, status='CANCELLED')
            t = self.db.task(ident)
            if t['case_id']:
                self.db.update_case(t['case_id'], phase='CANCELLED')
        elif self.db.case(ident):
            c = self.db.case(ident)
            self.db.update_case(ident, phase='CANCELLED')
            self.db.update_task(c['task_id'], status='CANCELLED')
        else:
            raise ValueError('unknown id')

    def retry(self, ident: str) -> None:
        """Re-run a BLOCKED/FAILED task from triage, or a FAILED case from its last Pro wait."""
        t = self.db.task(ident)
        if t and t['status'] == 'WAIT_OWNER' and t['data'].get('env_wait'):
            self.tasks.env_retry(ident)       # environment fixed: run the checks again
            return
        if t and t['status'] == 'WAIT_OWNER' and t['data'].get('spec_wait'):
            self.tasks.spec_more(ident)       # one more spec loop
            return
        if t and t['status'] in ('BLOCKED', 'FAILED'):
            self.db.event('call_budget_reset', ident)             # a retry gets a fresh call budget
            self.db.update_task(ident, status='TRIAGED' if t['tier'] else 'NEW', passes=0, lane_passes=0)
            return
        raise ValueError('only BLOCKED or FAILED tasks can be retried')

    # ------------------------------------------------------------------ loop
    def recover(self) -> None:
        self.db.x('UPDATE tasks SET busy=0')
        self.db.x('UPDATE cases SET busy=0')

    def _run(self, kind: str, ident: str, fn, item: dict) -> None:
        try:
            fn(item)
        except Exception as exc:
            self.db.event('step_error', item.get('task_id') if kind == 'case' else ident,
                          ident if kind == 'case' else None, error=repr(exc),
                          trace=traceback.format_exc()[-3000:])
            fails = item['data'].get('step_errors', 0) + 1
            item['data']['step_errors'] = fails
            if kind == 'task':
                cur = self.db.task(ident)
                cur['data']['step_errors'] = fails
                self.db.update_task(ident, data=cur['data'])
                if fails >= 3:
                    self.db.update_task(ident, status='BLOCKED', result=f'error: {exc}')
                    self.n.send(f'Blocked {ident}', f'Repeated error: {exc}', tags='warning')
            else:
                cur = self.db.case(ident)
                cur['data']['step_errors'] = fails
                self.db.update_case(ident, data=cur['data'])
                if fails >= 3:
                    self.db.update_case(ident, phase='PAUSED')
                    self.n.send(f'Paused {ident}', f'Repeated error: {exc}\nFix, then aa answer "resume {ident}"',
                                tags='warning')
        finally:
            table = 'tasks' if kind == 'task' else 'cases'
            self.db.x(f'UPDATE {table} SET busy=0 WHERE id=?', (ident,))

    def tick(self, pool: ThreadPoolExecutor | None = None, *, now: float | None = None) -> int:
        """Advance everything once. Returns the number of steps scheduled."""
        now = time.time() if now is None else now
        for line in self.db.inbox_take() + self.n.poll_replies():
            self.handle_reply(line)
        scheduled = 0
        poll_s = float(self.cfg['deep']['poll_s'])
        for t in self.db.tasks(tasks.ACTIVE):
            if not t['busy'] and not self._over_call_cap(t['id']):
                scheduled += self._submit(pool, 'task', t['id'], self.tasks.step, t)
        for c in self.db.cases(cases.ACTIVE):
            if c['busy']:
                continue
            if c['phase'] == 'WAIT_PRO' and now - c['data'].get('last_poll', 0) < poll_s:
                continue
            if c['phase'] == 'WAIT_PRO':
                c['data']['last_poll'] = now
                self.db.update_case(c['id'], data=c['data'])
            scheduled += self._submit(pool, 'case', c['id'], self.cases.step, c)
        return scheduled

    def _submit(self, pool, kind: str, ident: str, fn, item: dict) -> int:
        table = 'tasks' if kind == 'task' else 'cases'
        with self.db.lock:
            if self.db.q(f'SELECT busy FROM {table} WHERE id=?', (ident,))[0]['busy']:
                return 0
            self.db.x(f'UPDATE {table} SET busy=1 WHERE id=?', (ident,))
        if pool is None:
            self._run(kind, ident, fn, item)
        else:
            pool.submit(self._run, kind, ident, fn, item)
        return 1

    def serve(self) -> None:
        self.recover()
        stop = threading.Event()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        self.db.event('daemon_start')
        with ThreadPoolExecutor(max_workers=int(self.cfg['workers']['max_parallel'])) as pool:
            while not stop.is_set():
                try:
                    self.tick(pool)
                except Exception as exc:
                    self.db.event('tick_error', error=repr(exc), trace=traceback.format_exc()[-3000:])
                stop.wait(float(self.cfg['daemon']['tick_s']))
        self.db.event('daemon_stop')
