"""Local task flow: triage -> (owner pick) -> checks -> worker -> verify -> deliver/retry/escalate.

Status machine (tasks.status):
  NEW -> TRIAGED -> READY -> VERIFY -> DONE
  WAIT_OWNER (tier disagreement or unconfirmed checks), DEEP (handed to a case),
  BLOCKED (worker needs the owner), FAILED, CANCELLED.
Each step is idempotent: a crashed daemon resumes from the stored status.
"""
from __future__ import annotations

import string
from pathlib import Path

from . import checks as checks_mod
from . import git
from .config import Config
from .db import DB
from .notify import Notifier
from .decisions import PEER_LANES, peer_question, tier_question
from .workers import LANES, BillingError, Workers

PROMPTS = Path(__file__).parent / 'prompts'

TIERS = {
    'routine': 'A narrow mechanical change with a known contract: rename, config tweak, '
               'one-place fix, formatting, trivial documentation.',
    'bounded': 'A substantive but bounded implementation or debugging task inside the existing '
               'design: one feature or bug across a few files with clear acceptance.',
    'medium_tough': 'Medium-tough implementation inside an existing or approved design: several '
                    'interacting components, non-obvious logic, concurrency, performance or hard '
                    'debugging, but no new architecture.',
    'tough': 'Tough work: architecture or system design, research, security design, data '
             'migration design, irreversible changes, or a problem whose approach is unclear.',
}
TIER_ORDER = list(TIERS)
PRO_CATEGORIES = {'architecture', 'research', 'security_design', 'migration_design',
                  'irreversible_change_design'}
TIER_LANE = {'routine': 'luna_low', 'bounded': 'luna_high'}
MEDIUM_PEERS = tuple(PEER_LANES.values())      # model-only choice: astra_high | opus_high

TRIAGE_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['tier', 'pro_categories', 'summary', 'acceptance_criteria', 'relevant_paths', 'risks'],
    'properties': {
        'tier': {'type': 'string', 'enum': TIER_ORDER},
        'pro_categories': {'type': 'array', 'items': {'type': 'string', 'enum': sorted(PRO_CATEGORIES)}},
        'summary': {'type': 'string'},
        'acceptance_criteria': {'type': 'array', 'items': {'type': 'string'}},
        'relevant_paths': {'type': 'array', 'items': {'type': 'string'}},
        'risks': {'type': 'array', 'items': {'type': 'string'}},
    },
}

ACTIVE = ('NEW', 'TRIAGED', 'READY', 'VERIFY')


def render(name: str, **values: object) -> str:
    return string.Template((PROMPTS / name).read_text()).safe_substitute(
        {k: str(v) for k, v in values.items()})


def bullet(items: list[str] | None, empty: str = '- (none given)') -> str:
    return '\n'.join(f'- {x}' for x in items) if items else empty


class TaskFlow:
    def __init__(self, cfg: Config, db: DB, workers: Workers, decider, notifier: Notifier):
        # decider: aa.semif.SemIf (default) or aa.clm.CLM — same choose/rank interface.
        self.cfg, self.db, self.workers, self.decider, self.n = cfg, db, workers, decider, notifier

    # ------------------------------------------------------------------ intake
    def create(self, repo: Path, prompt: str, tier: str | None = None) -> str:
        if tier is not None and tier not in TIERS:
            raise ValueError(f'unknown tier {tier}')
        top = git.toplevel(repo)
        tid = self.db.create_task(str(top), prompt, tier)
        self.db.update_task(tid, base_ref=git.head(top))
        return tid

    def step(self, t: dict) -> None:
        handler = {'NEW': self._triage, 'TRIAGED': self._route, 'READY': self._work,
                   'VERIFY': self._verify}.get(t['status'])
        if handler:
            handler(t)

    # ------------------------------------------------------------------ triage
    def _triage(self, t: dict) -> None:
        repo = Path(t['repo'])
        data = t['data']
        prompt = render('triage.md', repo=repo, prompt=t['prompt'],
                        **{f'tier_{k}': v for k, v in TIERS.items()})
        res = self.workers.execute(LANES['luna_high'] if self.cfg['triage']['effort'] == 'high'
                                   else LANES['luna_low'], prompt, repo, write=False,
                                   schema=TRIAGE_SCHEMA, log_name=f'{t["id"]}-triage')
        if not res.ok or not res.structured:
            self.db.event('triage_failed', t['id'], error=res.error[:500])
            triage = {'tier': None, 'pro_categories': [], 'summary': '', 'acceptance_criteria': [],
                      'relevant_paths': [], 'risks': []}
        else:
            triage = res.structured
        data['triage'] = triage
        codex_tier = triage.get('tier')
        if triage.get('pro_categories'):
            codex_tier = 'tough'

        question, options = tier_question(self._backend())
        clm_tier, probs, did = self.decider.choose('tier', t['id'], t['prompt'], question, options)
        if not self._confident(probs):
            clm_tier = None            # Near-uniform scores are an abstention, not a vote.
        data['tier_votes'] = {'codex': codex_tier, 'decider': clm_tier, 'backend': self._backend(),
                              'probs': probs, 'decision_id': did}

        if t['tier']:                      # Owner fixed the tier at intake.
            final, source = t['tier'], 'owner'
        elif codex_tier and clm_tier and codex_tier != clm_tier:
            self.db.update_task(t['id'], data=data, status='WAIT_OWNER')
            self._ask_tier(t, codex_tier, clm_tier, triage.get('summary', ''))
            return
        elif codex_tier or clm_tier:
            final = codex_tier or clm_tier
            source = 'agree' if codex_tier == clm_tier else ('codex' if codex_tier else 'clm')
        else:
            self.db.update_task(t['id'], data=data, status='WAIT_OWNER')
            self._ask_tier(t, None, None, 'Triage failed on both Codex and CLM.')
            return
        self.db.decision_final(did, final)
        self.db.update_task(t['id'], tier=final, tier_source=source, data=data, status='TRIAGED')

    def _ask_tier(self, t: dict, codex_tier: str | None, clm_tier: str | None, summary: str) -> None:
        opts = [x for x in (codex_tier, clm_tier) if x] or ['bounded', 'medium_tough', 'tough']
        higher = [x for x in TIER_ORDER if TIER_ORDER.index(x) > max(TIER_ORDER.index(o) for o in opts)]
        if len(opts) < 3 and higher:
            opts.append(higher[0])
        self.n.send(f'Tier? {t["id"]}',
                    f'{t["prompt"][:300]}\n\nCodex: {codex_tier}  {self._backend()}: {clm_tier}\n{summary[:500]}\n'
                    f'Or on the workstation: aa answer "tier {t["id"]} <tier>"',
                    choices=[(o, f'tier {t["id"]} {o}') for o in opts[:3]], priority=4, tags='question')

    def set_tier(self, tid: str, tier: str) -> None:
        t = self.db.task(tid)
        if not t or tier not in TIERS:
            raise ValueError('unknown task or tier')
        did = (t['data'].get('tier_votes') or {}).get('decision_id')
        if did:
            self.db.decision_final(did, tier)
        self.db.update_task(tid, tier=tier, tier_source='owner_pick', status='TRIAGED')

    # ----------------------------------------------------------------- routing
    def _route(self, t: dict) -> None:
        if not self._checks_ready(t):
            return
        if t['tier'] == 'tough':
            self._to_deep(t, 'tier tough')
            return
        lane = TIER_LANE.get(t['tier']) or self._choose_peer(t, exclude=())
        self._start_lane(t, lane)

    def _backend(self) -> str:
        return getattr(self.decider, 'backend', 'clm')

    def _choose_peer(self, t: dict, exclude: tuple[str, ...]) -> str | None:
        """Pick the medium-tough MODEL (Astra or Opus); effort per model is fixed."""
        question, texts = peer_question(self._backend())
        options = {k: v for k, v in texts.items() if PEER_LANES[k] not in exclude}
        if not options:
            return None
        if len(options) == 1:
            return PEER_LANES[next(iter(options))]
        pick, probs, did = self.decider.choose('peer', t['id'], t['prompt'], question, options)
        if not self._confident(probs):
            pick = None
        final = pick if pick in options else 'astra'      # deterministic default
        self.db.decision_final(did, final)
        return PEER_LANES[final]

    def _confident(self, probs: dict | None) -> bool:
        """Decider confidence (top minus mean of the rest) must reach decider.min_confidence."""
        if not probs:
            return False
        vals = sorted(probs.values(), reverse=True)
        conf = vals[0] - sum(vals[1:]) / max(1, len(vals) - 1)
        return conf >= float(self.cfg['decider'].get('min_confidence', 0.2))

    def _start_lane(self, t: dict, lane: str | None) -> None:
        if lane is None:
            self._to_deep(t, 'implementation tiers exhausted')
            return
        tried = t['data'].setdefault('lanes_tried', [])
        if lane not in tried:
            tried.append(lane)
        self.db.update_task(t['id'], lane=lane, lane_passes=0, data=t['data'], status='READY')

    # ------------------------------------------------------------------ checks
    def _checks_ready(self, t: dict) -> bool:
        repo = Path(t['repo'])
        try:
            file_checks = checks_mod.from_file(repo)
        except ValueError as exc:
            self.db.update_task(t['id'], status='BLOCKED', result=str(exc))
            self.n.send(f'Blocked {t["id"]}', str(exc), tags='warning')
            return False
        if file_checks is not None:
            t['data']['checks'] = file_checks
            self.db.update_task(t['id'], data=t['data'])
            return True
        rec = self.db.repo_checks(str(repo))
        if rec and rec['confirmed']:
            t['data']['checks'] = rec['checks']
            self.db.update_task(t['id'], data=t['data'])
            return True
        detected = checks_mod.autodetect(repo)
        self.db.set_repo_checks(str(repo), detected, confirmed=False)
        self.db.update_task(t['id'], status='WAIT_OWNER')
        self.n.send(f'Confirm checks: {repo.name}',
                    'Autodetected checks (run after every task):\n' + (checks_mod.summary(
                        [checks_mod.CheckRun(k, v, 0, '') for k, v in detected.items()])
                        if detected else '(none found)') +
                    f'\n\nTo customise, add .agenticarch.toml [checks] to the repo, then reply ok.',
                    choices=[('OK', f'checks {t["id"]} ok'), ('No checks', f'checks {t["id"]} none')],
                    priority=4, tags='question')
        return False

    def confirm_checks(self, tid: str, answer: str) -> None:
        t = self.db.task(tid)
        if not t:
            raise ValueError('unknown task')
        rec = self.db.repo_checks(t['repo']) or {'checks': {}}
        checks = {} if answer == 'none' else rec['checks']
        self.db.set_repo_checks(t['repo'], checks, confirmed=True)
        self.db.update_task(tid, status='TRIAGED')

    # ----------------------------------------------------------------- working
    def _worktree(self, t: dict) -> Path:
        wt = self.cfg.worktrees / t['id']
        branch = t['branch'] or f'aa/{t["id"]}'
        git.add_worktree(Path(t['repo']), wt, branch, t['base_ref'])
        if t['worktree'] != str(wt) or t['branch'] != branch:
            self.db.update_task(t['id'], worktree=str(wt), branch=branch)
        return wt

    def _work(self, t: dict) -> None:
        lane = LANES[t['lane']]
        wt = self._worktree(t)
        tri = t['data'].get('triage') or {}
        prev = t['data'].get('last_failure')
        previous = (f'\nA previous attempt left the worktree as it is now but these checks failed '
                    f'(fix them; keep what works):\n{prev}\n') if prev else ''
        prompt = render('worker.md', worktree=wt, branch=t['branch'] or f'aa/{t["id"]}',
                        prompt=t['prompt'], acceptance=bullet(tri.get('acceptance_criteria')),
                        paths=', '.join(tri.get('relevant_paths') or []) or '(explore as needed)',
                        checks=bullet([f'{k}: `{v}`' for k, v in (t['data'].get('checks') or {}).items()],
                                      '- (none configured)'),
                        previous=previous)
        try:
            res = self.workers.execute(lane, prompt, wt, log_name=t['id'])
        except BillingError as exc:
            self.db.update_task(t['id'], status='BLOCKED', result=f'billing: {exc}')
            self.n.send(f'Blocked {t["id"]}', f'Subscription check failed: {exc}', tags='warning')
            return
        passes, lane_passes = t['passes'] + 1, t['lane_passes'] + 1
        t['data'].setdefault('attempts', []).append(
            {'lane': lane.name, 'ok': res.ok, 'seconds': round(res.seconds), 'usage': res.usage,
             'error': res.error[:500], 'summary': res.text[-1500:]})
        self.db.update_task(t['id'], passes=passes, lane_passes=lane_passes, data=t['data'])
        blocked = next((ln for ln in res.text.splitlines() if ln.startswith('BLOCKED:')), None)
        if blocked:
            self.db.update_task(t['id'], status='BLOCKED', result=blocked)
            self.n.send(f'Blocked {t["id"]}', blocked[:1000], tags='warning')
            return
        if not res.ok:
            t = self.db.task(t['id'])
            t['data']['last_failure'] = f'worker error: {res.error[:1500]}'
            self._retry_or_escalate(t)
            return
        # Snapshot the worker's changes so check artefacts (caches, builds) never get committed.
        git.commit_all(wt, f'aa wip {t["id"]} pass {passes} ({lane.name})')
        self.db.update_task(t['id'], status='VERIFY')

    def _verify(self, t: dict) -> None:
        wt = Path(t['worktree'])
        results = checks_mod.run(t['data'].get('checks') or {}, wt)
        git.discard(wt)                      # drop artefacts produced by the checks
        t['data']['checks_result'] = checks_mod.summary(results)
        if all(r.ok for r in results):
            self.db.decision_outcome(t['id'], 'tier', 'pass')
            self.db.decision_outcome(t['id'], 'peer', 'pass')
            self._deliver(t, results)
        else:
            t['data']['last_failure'] = checks_mod.failure_report(results)
            self.db.update_task(t['id'], data=t['data'])
            self._retry_or_escalate(t)

    def _retry_or_escalate(self, t: dict) -> None:
        r = self.cfg['retry']
        if t['passes'] >= r['max_total_passes']:
            self._to_deep(t, 'retry budget exhausted')
            return
        if t['lane_passes'] < r['max_passes_per_lane']:
            self.db.update_task(t['id'], status='READY', data=t['data'])
            return
        self.db.decision_outcome(t['id'], 'peer', 'fail')
        tried = tuple(t['data'].get('lanes_tried', []))
        if t['lane'] == 'luna_low':
            nxt = 'luna_high'
        elif t['lane'] == 'luna_high':
            nxt = self._choose_peer(t, exclude=tried)
        else:
            # Try the other medium-tough model before giving up on local implementation.
            nxt = next((p for p in MEDIUM_PEERS if p not in tried), None)
        self.db.event('escalate', t['id'], frm=t['lane'], to=nxt)
        self._start_lane(t, nxt)

    def _deliver(self, t: dict, results) -> None:
        wt = Path(t['worktree'])
        title = t['prompt'].strip().splitlines()[0][:72]
        git.git(wt, 'reset', '-q', '--soft', t['base_ref'])     # squash the wip snapshots
        sha = git.commit_all(wt, f'aa: {title}\n\nTask {t["id"]} via {t["lane"]}.\n'
                                 f'Checks:\n{checks_mod.summary(results)}')
        stat = git.diffstat(wt, t['base_ref'])
        pushed = ''
        if sha and self.cfg['delivery']['push_branch'] and git.github_slug(Path(t['repo'])):
            try:
                git.git(wt, 'push', '-u', 'origin', t['branch'])
                pushed = f' (pushed to origin/{t["branch"]})'
            except git.GitError as exc:
                pushed = f' (push failed: {exc})'
        result = f'branch {t["branch"]}{pushed}; commit {sha or "no changes"}'
        self.db.update_task(t['id'], status='DONE', result=result, data=t['data'])
        git.remove_worktree(Path(t['repo']), wt)
        self.n.send(f'Done {t["id"]} ({t["lane"]})',
                    f'{title}\n{result}\n{t["data"]["checks_result"]}\n{stat[-800:]}', tags='white_check_mark')

    # -------------------------------------------------------------------- deep
    def _to_deep(self, t: dict, reason: str) -> None:
        self.db.event('to_deep', t['id'], reason=reason)
        if t['case_id']:
            return
        cid = self.db.create_case(t['id'])
        self.db.update_task(t['id'], status='DEEP', case_id=cid, tier='tough',
                            result=f'deep case {cid}: {reason}')
