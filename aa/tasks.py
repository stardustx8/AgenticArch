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
from .quality import QualityMixin, cleanup_quality_worktrees
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
    'required': ['tier', 'peer', 'pro_categories', 'summary', 'acceptance_criteria', 'relevant_paths', 'risks',
                 'owner_question', 'testable'],
    'properties': {
        'testable': {'type': 'boolean'},
        'owner_question': {'type': 'string'},
        'tier': {'type': 'string', 'enum': TIER_ORDER},
        'peer': {'type': 'string', 'enum': sorted(PEER_LANES)},
        'pro_categories': {'type': 'array', 'items': {'type': 'string', 'enum': sorted(PRO_CATEGORIES)}},
        'summary': {'type': 'string'},
        'acceptance_criteria': {'type': 'array', 'items': {'type': 'string'}},
        'relevant_paths': {'type': 'array', 'items': {'type': 'string'}},
        'risks': {'type': 'array', 'items': {'type': 'string'}},
    },
}

ACTIVE = ('NEW', 'TRIAGED', 'ORACLE', 'MAP', 'RACE', 'READY', 'VERIFY', 'SPEC', 'DELIVER')

WORKER_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['status', 'summary', 'open_items', 'question', 'rebuttals', 'spec_conflicts'],
    'properties': {
        'spec_conflicts': {'type': 'array', 'items': {'type': 'string'}},
        'status': {'type': 'string', 'enum': ['done', 'partial', 'blocked']},
        'summary': {'type': 'string'},
        'open_items': {'type': 'array', 'items': {'type': 'string'}},
        'question': {'type': 'string'},
        'rebuttals': {'type': 'array', 'items': {'type': 'string'}},
    },
}

SPEC_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['criteria', 'tampering', 'tampering_reason'],
    'properties': {
        'criteria': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['index', 'criterion', 'met', 'reason'],
            'properties': {'index': {'type': 'integer'}, 'criterion': {'type': 'string'},
                           'met': {'type': 'boolean'}, 'reason': {'type': 'string'}}}},
        'tampering': {'type': 'boolean'},
        'tampering_reason': {'type': 'string'},
    },
}


def worker_report(res) -> dict:
    """Structured worker status; falls back to the legacy text markers when absent."""
    s = res.structured if isinstance(res.structured, dict) else None
    if s and s.get('status') in ('done', 'partial', 'blocked'):
        return {'status': s['status'], 'summary': str(s.get('summary', '')),
                'open_items': [str(x) for x in s.get('open_items') or []],
                'question': str(s.get('question', '')), 'rebuttals': [str(x) for x in s.get('rebuttals') or []],
                'spec_conflicts': [str(x) for x in s.get('spec_conflicts') or []], 'from_schema': True}
    lines = res.text.splitlines()
    blocked = next((ln for ln in lines if ln.startswith('BLOCKED:')), None)
    return {'status': 'blocked' if blocked else 'done', 'summary': res.text,
            'open_items': [], 'question': blocked[len('BLOCKED:'):].strip() if blocked else '',
            'rebuttals': [ln.strip() for ln in lines if ln.strip().startswith('REBUTTAL:')],
            'spec_conflicts': [], 'from_schema': False}


def render(name: str, **values: object) -> str:
    return string.Template((PROMPTS / name).read_text()).safe_substitute(
        {k: str(v) for k, v in values.items()})


def bullet(items: list[str] | None, empty: str = '- (none given)') -> str:
    return '\n'.join(f'- {x}' for x in items) if items else empty


class TaskFlow(QualityMixin):
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
        handler = {'NEW': self._triage, 'TRIAGED': self._route, 'ORACLE': self._oracle, 'RACE': self._race,
                   'MAP': self._map,
                   'READY': self._work,
                   'VERIFY': self._verify, 'SPEC': self._spec_check,
                   'DELIVER': self._deliver}.get(t['status'])
        if handler:
            handler(t)

    # ------------------------------------------------------------------ triage
    def _triage(self, t: dict) -> None:
        repo = Path(t['repo'])
        data = t['data']
        prompt = render('triage.md', repo=repo, prompt=t['prompt'], owner_answers=self._answers_text(t),
                        **{f'tier_{k}': v for k, v in TIERS.items()})
        try:
            res = self.workers.execute(LANES['luna_high'] if self.cfg['triage']['effort'] == 'high'
                                       else LANES['luna_low'], prompt, repo, write=False,
                                       schema=TRIAGE_SCHEMA, log_name=f'{t["id"]}-triage')
        except BillingError as exc:              # triage falls back to the local decider
            from .workers import Result
            res = Result(False, '', error=f'billing: {exc}')
            self.n.send('Codex login problem', str(exc), tags='warning')
        if not res.ok or not res.structured:
            self.db.event('triage_failed', t['id'], error=res.error[:500])
            triage = {'tier': None, 'pro_categories': [], 'summary': '', 'acceptance_criteria': [],
                      'relevant_paths': [], 'risks': []}
        else:
            triage = res.structured
        data['triage'] = triage
        if (triage.get('owner_question') or '').strip() and not self._questions_exhausted(t):
            # Missing owner facts are asked before anyone is dispatched (not routed to Pro).
            data['question_stage'] = 'triage'
            self.db.update_task(t['id'], data=data)
            self._ask_owner(t, triage['owner_question'].strip())
            return
        codex_tier = triage.get('tier')
        if triage.get('pro_categories'):
            codex_tier = 'tough'

        question, options = tier_question(self._backend())
        clm_tier, probs, did = self.decider.choose('tier', t['id'], t['prompt'], question, options)
        if not self._confident(probs):
            clm_tier = None            # Near-uniform scores are an abstention, not a vote.
        data['tier_votes'] = {'codex': codex_tier, 'decider': clm_tier, 'backend': self._backend(),
                              'probs': probs, 'decision_id': did}

        policy = self.cfg['triage'].get('policy', 'codex')
        if t['tier']:                      # Owner fixed the tier at intake.
            final, source = t['tier'], 'owner'
        elif not codex_tier and not clm_tier:
            self.db.update_task(t['id'], data=data, status='WAIT_OWNER')
            self._ask_tier(t, None, None, 'Triage failed on both Codex and the local decider.')
            return
        elif not codex_tier or not clm_tier or codex_tier == clm_tier:
            final = codex_tier or clm_tier
            source = 'agree' if codex_tier == clm_tier else ('codex' if codex_tier else 'decider')
        elif policy == 'codex':
            # Benchmark: Codex alone had the lowest error cost; the decider vote is kept
            # in the log (shadow) and used only when Codex triage fails.
            final, source = codex_tier, 'codex'
        elif policy == 'higher_if_1' and abs(TIER_ORDER.index(codex_tier) - TIER_ORDER.index(clm_tier)) == 1:
            final = max(codex_tier, clm_tier, key=TIER_ORDER.index)
            source = 'higher_vote'
        else:                              # ask_on_disagreement, or higher_if_1 with a 2+ gap
            self.db.update_task(t['id'], data=data, status='WAIT_OWNER')
            self._ask_tier(t, codex_tier, clm_tier, triage.get('summary', ''))
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
        self._plan_quality(t, lane)          # oracle tests / best-of-2 triggers, then the lane

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
        codex_peer = (t['data'].get('triage') or {}).get('peer')
        if self.cfg['triage'].get('policy', 'codex') == 'codex' and codex_peer in options:
            pick = codex_peer                              # decider vote stays logged (shadow)
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
        git.add_worktree(Path(t['repo']), wt, branch, self._start_commit(t))
        if t['worktree'] != str(wt) or t['branch'] != branch:
            self.db.update_task(t['id'], worktree=str(wt), branch=branch)
        return wt

    def _work(self, t: dict) -> None:
        lane = LANES[t['lane']]
        wt = self._worktree(t)
        tri = t['data'].get('triage') or {}
        prev = t['data'].get('last_failure')
        previous = self._oracle_worker_note(t) + ((f'\nA previous attempt left the worktree as it is now. '
                    f'Feedback on it (address it; keep what works):\n{prev}\n') if prev else '')
        owner_answers = self._answers_text(t)
        prompt = render('worker.md', worktree=wt, branch=t['branch'] or f'aa/{t["id"]}',
                        prompt=t['prompt'], acceptance=bullet(tri.get('acceptance_criteria')),
                        paths=', '.join(tri.get('relevant_paths') or []) or '(explore as needed)',
                        checks=bullet([f'{k}: `{v}`' for k, v in (t['data'].get('checks') or {}).items()],
                                      '- (none configured)'),
                        previous=previous, owner_answers=owner_answers, ideas=self._idea_notes(t))
        try:
            res = self.workers.execute(lane, prompt, wt, schema=WORKER_SCHEMA, log_name=t['id'])
        except BillingError as exc:
            self.db.update_task(t['id'], status='BLOCKED', result=f'billing: {exc}')
            self.n.send(f'Blocked {t["id"]}', f'Subscription check failed: {exc}', tags='warning')
            return
        report = worker_report(res)
        free_rerun = t['data'].pop('spec_rerun', False) or t['data'].pop('answer_rerun', False)
        passes = t['passes'] + (0 if free_rerun else 1)         # spec loops / owner answers: own budget
        lane_passes = t['lane_passes'] + (0 if free_rerun else 1)
        t['data'].setdefault('attempts', []).append(
            {'lane': lane.name, 'ok': res.ok, 'seconds': round(res.seconds), 'usage': res.usage,
             'error': res.error[:500], 'status': report['status'], 'summary': report['summary'][-1500:]})
        if report['rebuttals']:
            t['data']['rebuttals'] = report['rebuttals'][:10]
        if report['spec_conflicts']:
            t['data']['spec_conflicts'] = report['spec_conflicts'][:10]
            if self._disputed_oracle_files(t, report['spec_conflicts']):   # conflicts with the oracle = dispute
                t['data']['rebuttals'] = (t['data'].get('rebuttals') or []) + report['spec_conflicts'][:5]
        # A worker that stops because an independent test is wrong: the coordinator checks the claim
        # itself (_verify drops those tests only if they are all that fails) instead of asking the owner.
        stop_texts = [x for x in (report['question'], *report['open_items']) if x]
        disputed = (report['status'] in ('partial', 'blocked') and
                    self._disputed_oracle_files(t, stop_texts + [report['summary']]))
        if disputed:
            t['data']['rebuttals'] = (t['data'].get('rebuttals') or []) + (stop_texts or [report['summary']])[:5]
            self.db.event('oracle_disputed', t['id'], status=report['status'], files=disputed[:10])
        self.db.update_task(t['id'], passes=passes, lane_passes=lane_passes, data=t['data'])
        if report['status'] == 'blocked' and not disputed:
            if self._questions_exhausted(t):
                # Owner answers are free reruns, so an ever-blocking worker would loop on the owner.
                t = self.db.task(t['id'])
                t['data']['last_failure'] = ('You reported blocked again although the owner already answered '
                                             'your questions (see above). Do not ask again: decide from those '
                                             'answers, state your assumptions in the summary and finish.')
                self.db.event('owner_questions_exhausted', t['id'], question=report['question'][:300])
                self._retry_or_escalate(t)
                return
            self._ask_owner(t, report['question'] or report['summary'])
            return
        if not res.ok and not report['from_schema']:
            t = self.db.task(t['id'])
            t['data']['last_failure'] = f'worker error: {res.error[:1500]}'
            self._retry_or_escalate(t)
            return
        if report['status'] == 'partial' and not disputed:
            # No point running checks on known-incomplete work: send it straight back.
            t = self.db.task(t['id'])
            t['data']['last_failure'] = ('You reported the task as partial. Still required:\n' +
                                         bullet(report['open_items'], '- (see your summary)'))
            self.db.event('worker_partial', t['id'], open_items=report['open_items'][:10])
            self._retry_or_escalate(t)
            return
        self._protect_oracle(t, wt)          # independent tests are read-only for workers
        self.db.update_task(t['id'], data=t['data'])
        # Snapshot the worker's changes so check artefacts (caches, builds) never get committed.
        git.commit_all(wt, f'aa wip {t["id"]} pass {passes} ({lane.name})')
        self.db.update_task(t['id'], status='VERIFY')

    # ------------------------------------------------------- owner questions
    def _ask_owner(self, t: dict, question: str) -> None:
        t = self.db.task(t['id'])
        t['data']['worker_question'] = question
        self.db.update_task(t['id'], status='WAIT_OWNER', data=t['data'])
        self.db.event('worker_blocked', t['id'], question=question[:500])
        self.n.send(f'Question from worker: {t["id"]}',
                    f'{t["prompt"][:160]}\n\n{question[:2500]}\n\nAnswer: publish "answer {t["id"]} <your answer>" '
                    f'to topic {self.n.reply_topic} in ntfy, or on the workstation: '
                    f'aa answer "answer {t["id"]} <your answer>"',
                    choices=[('Cancel', f'cancel {t["id"]}')], priority=4, tags='question')

    def _questions_exhausted(self, t: dict) -> bool:
        return len(t['data'].get('owner_answers') or []) >= int(self.cfg['retry'].get('max_owner_questions', 3))

    @staticmethod
    def _answers_text(t: dict) -> str:
        answers = t['data'].get('owner_answers') or []
        return ('\nThe owner answered these questions (treat as facts):\n' +
                '\n'.join(f'- Q: {a["q"]}\n  A: {a["a"]}' for a in answers) + '\n') if answers else ''

    def answer_worker(self, tid: str, text: str) -> None:
        t = self.db.task(tid)
        if not t or t['status'] != 'WAIT_OWNER' or not t['data'].get('worker_question'):
            raise ValueError('task is not waiting on a question')
        t['data'].setdefault('owner_answers', []).append({'q': t['data'].pop('worker_question'), 'a': text.strip()})
        if t['data'].pop('question_stage', None) == 'triage':
            self.db.update_task(tid, status='NEW', data=t['data'])      # re-triage with the answer
            return
        t['data']['answer_rerun'] = True
        self.db.update_task(tid, status='READY', data=t['data'])

    def _verify(self, t: dict) -> None:
        wt = Path(t['worktree'])
        results = checks_mod.run(t['data'].get('checks') or {}, wt)
        git.discard(wt)                      # drop artefacts produced by the checks
        t['data']['checks_result'] = checks_mod.summary(results)
        failed = [r for r in results if not r.ok]
        disputed = self._disputed_oracle_files(t, t['data'].get('rebuttals') or [])
        if disputed and self._fails_only_by_oracle(t, wt, failed):
            self._drop_oracle(t, 'the implementer passed everything except the acceptance tests it disputed: ' +
                              ' '.join(t['data']['rebuttals'])[:300], wts=[wt], disputed=disputed)
            self.db.update_task(t['id'], data=t['data'])      # stays in VERIFY: re-run the checks without them
            return
        if failed and self.cfg['failure_triage'].get('enabled', True):
            failed = self._triage_failures(t, wt, failed)
            if failed is None:               # paused for the owner (environment problem)
                return
        if not failed:
            self.db.update_task(t['id'], data=t['data'])     # persist check notes before the gate reloads
            self._mutation_gate(t, wt)
            t = self.db.task(t['id'])
            self._post_check_ideas(t, wt)                    # diff audit / attacker (flags)
            t = self.db.task(t['id'])
            self.db.decision_outcome(t['id'], 'tier', 'pass')
            self.db.decision_outcome(t['id'], 'best_of_2', 'pass')
            self.db.decision_outcome(t['id'], 'peer', 'pass')
            if self.cfg['spec_check'].get('enabled', True):
                self.db.update_task(t['id'], status='SPEC', data=t['data'])
            else:
                self.db.update_task(t['id'], status='DELIVER', data=t['data'])
        else:
            t['data']['last_failure'] = checks_mod.failure_report(failed)
            self.db.update_task(t['id'], data=t['data'])
            self._retry_or_escalate(t)

    # ------------------------------------------------------- failure triage
    def _base_wt(self, t: dict) -> Path:
        path = self.cfg.state_dir / 'base-wt' / t['id']
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            git.git(Path(t['repo']), 'worktree', 'add', '--detach', str(path), t['base_ref'])
        return path

    def _triage_failures(self, t: dict, wt: Path, failed: list) -> list | None:
        """FLAKY and PRE_EXISTING failures do not block; ENVIRONMENT pauses; CODE is returned."""
        from .failure_triage import triage
        cache = t['data'].setdefault('base_checks', {})

        def run_on_base(cmd: str) -> checks_mod.CheckRun:
            if cmd not in cache:
                r = checks_mod.run({'base': cmd}, self._base_wt(t))[0]
                git.discard(self._base_wt(t))
                cache[cmd] = [r.exit_code, r.output]
            code, out = cache[cmd]
            return checks_mod.CheckRun('base', cmd, code, out)

        # Oracle tests fail on the base commit by design, so they are never PRE_EXISTING.
        oracle_failed = [r for r in failed if r.name == 'oracle_tests']
        verdicts = [triage(r, wt, run_on_base, self.decider, task_id=t['id'],
                           min_confidence=float(self.cfg['failure_triage']['min_confidence']))
                    for r in failed if r.name != 'oracle_tests']
        git.discard(wt)                      # artefacts from the reruns
        notes = t['data'].setdefault('triage_notes', {})
        spec_on = self.cfg['spec_check'].get('enabled', True)
        for v in verdicts:
            if v.action == 'PRE_EXISTING' and not spec_on:
                v.action = 'CODE'            # without the spec judge nobody decides if it had to be fixed
            if v.action in ('FLAKY', 'PRE_EXISTING'):
                notes[v.check] = v.action
        self.db.event('failure_triage', t['id'], verdicts={v.check: v.action for v in verdicts})
        env = [v for v in verdicts if v.action == 'ENVIRONMENT']
        if env:
            outputs = {r.name: r.output for r in failed}
            t['data']['env_wait'] = True
            t['data']['env_failures'] = checks_mod.failure_report([r for r in failed if r.name in {v.check for v in env}])
            self.db.update_task(t['id'], status='WAIT_OWNER', data=t['data'])
            detail = '\n'.join(f'{v.check}: {outputs[v.check].strip().splitlines()[-1][:200] if outputs[v.check].strip() else ""}'
                               for v in env)
            self.n.send(f'Environment problem: {t["id"]}',
                        f'{t["prompt"][:160]}\nThese checks fail because of the machine/setup, not the code:\n'
                        f'{detail}\nFix the environment, then Retry. Or treat it as a code failure.',
                        choices=[('Retry', f'retry {t["id"]}'), ('Treat as code', f'code {t["id"]}'),
                                 ('Cancel', f'cancel {t["id"]}')], priority=4, tags='wrench')
            return None
        codes = {v.check for v in verdicts if v.action == 'CODE'}
        return [r for r in failed if r.name in codes] + oracle_failed

    def env_retry(self, tid: str) -> None:
        t = self.db.task(tid)
        t['data']['env_wait'] = False
        t['data'].get('base_checks', {}).clear()
        self.db.update_task(tid, status='VERIFY', data=t['data'])

    def env_as_code(self, tid: str) -> None:
        t = self.db.task(tid)
        if not t or not t['data'].get('env_wait'):
            raise ValueError('task is not paused on an environment problem')
        t['data']['env_wait'] = False
        t['data']['last_failure'] = t['data'].get('env_failures', '')
        self.db.update_task(tid, data=t['data'])
        self._retry_or_escalate(self.db.task(tid))

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
        elif t['lane'] == 'luna_high' and self.cfg['best_of_2'].get('on_escalation', True) \
                and self.cfg['best_of_2'].get('enabled', True):
            self.db.event('escalate', t['id'], frm=t['lane'], to='best_of_2')
            t['data']['mode'] = 'race'
            self.db.update_task(t['id'], data=t['data'], status='RACE')
            return
        elif t['lane'] == 'luna_high':
            nxt = self._choose_peer(t, exclude=tried)
        else:
            # Try the other medium-tough model before giving up on local implementation.
            nxt = next((p for p in MEDIUM_PEERS if p not in tried), None)
        self.db.event('escalate', t['id'], frm=t['lane'], to=nxt)
        self._start_lane(t, nxt)

    # ------------------------------------------------------------ spec check
    def _spec_check(self, t: dict) -> None:
        """Independent Opus review of every acceptance criterion against the committed diff."""
        sc = self.cfg['spec_check']
        wt = Path(t['worktree'])
        # Without triage criteria (e.g. Codex triage failed) the task statement is the criterion.
        criteria = ((t['data'].get('triage') or {}).get('acceptance_criteria') or
                    ['The task is fully implemented exactly as stated above.'])
        diff = git.git(wt, 'diff', f'{t["base_ref"]}..HEAD', check=False)
        if len(diff) > 60000:
            diff = diff[:60000] + '\n[diff truncated; read the files in the worktree]'
        rebuttals = t['data'].get('rebuttals') or []
        pre = [k for k, v in (t['data'].get('triage_notes') or {}).items() if v == 'PRE_EXISTING']
        check_note = (f'\nNote: these required checks still FAIL, exactly as they did on the base commit '
                      f'before the change: {", ".join(pre)}. If the task or a criterion requires them to '
                      f'pass, that criterion is unmet.\n' if pre else '')
        prompt = render('spec_judge.md', worktree=wt, prompt=t['prompt'], base=t['base_ref'][:12],
                        criteria='\n'.join(f'{i + 1}. {c}' for i, c in enumerate(criteria)), diff=diff,
                        rebuttals=(('\nThe worker rebutted earlier findings:\n' + '\n'.join(rebuttals) + '\n')
                                   if rebuttals else '') + check_note + self._quality_note_for_judge(t))
        res = self.workers.execute(LANES[sc['lane']], prompt, wt, write=False, schema=SPEC_SCHEMA,
                                   log_name=f'{t["id"]}-spec')
        if not res.ok or not res.structured:
            raise RuntimeError(f'spec judge failed: {res.error[:300]}')   # daemon retries, then BLOCKED
        verdict = res.structured
        judged = sorted(c.get('index') for c in verdict['criteria'] if isinstance(c.get('index'), int))
        if judged != list(range(1, len(criteria) + 1)):
            # An incomplete or duplicated verdict never counts as "all met": retry, then BLOCKED.
            raise RuntimeError(f'spec judge failed: judged criteria {judged}, expected 1..{len(criteria)}')
        unmet = [c for c in verdict['criteria'] if not c['met']]
        loops = t['data'].get('spec_loops', 0)
        t['data'].setdefault('spec_reviews', []).append(
            {'loop': loops, 'unmet': unmet, 'tampering': verdict['tampering'],
             'tampering_reason': verdict['tampering_reason'], 'seconds': round(res.seconds)})
        t['data'].pop('rebuttals', None)
        if not unmet and not verdict['tampering']:
            self.db.update_task(t['id'], status='DELIVER', data=t['data'])
            return
        feedback = self._spec_feedback(unmet, verdict)
        if loops >= int(sc['max_loops']) + t['data'].get('spec_extra', 0):
            t['data']['spec_wait'] = True
            self.db.update_task(t['id'], status='WAIT_OWNER', data=t['data'])
            self.n.send(f'Spec not met: {t["id"]}',
                        f'{t["prompt"][:200]}\nAfter {loops} spec loop(s) the reviewer still reports:\n'
                        f'{feedback[:2500]}',
                        choices=[('Accept', f'accept {t["id"]}'), ('One more', f'retry {t["id"]}'),
                                 ('Cancel', f'cancel {t["id"]}')], priority=4, tags='mag')
            return
        self._send_back(t, feedback)

    @staticmethod
    def _spec_feedback(unmet: list[dict], verdict: dict) -> str:
        lines = [f'- UNMET: {c["criterion"]} — {c["reason"]}' for c in unmet]
        if verdict['tampering']:
            lines.append(f'- TAMPERING: {verdict["tampering_reason"]}')
        return '\n'.join(lines)

    def _send_back(self, t: dict, feedback: str) -> None:
        t['data']['spec_loops'] = t['data'].get('spec_loops', 0) + 1
        t['data']['spec_rerun'] = True
        t['data']['last_failure'] = (
            f'An independent reviewer (spec loop {t["data"]["spec_loops"]}) found the implementation does '
            f'not yet meet the specification. The checks pass; do not weaken them.\n{feedback}\n'
            'Fix these points. If you are sure a point is already satisfied, do not change code for it; '
            'instead add an entry to `rebuttals` citing the file and lines that satisfy it.')
        self.db.event('spec_send_back', t['id'], loop=t['data']['spec_loops'])
        self.db.update_task(t['id'], status='READY', data=t['data'])

    def accept_spec(self, tid: str) -> None:
        t = self.db.task(tid)
        if not t or not t['data'].get('spec_wait'):
            raise ValueError('task is not waiting on a spec decision')
        t['data']['spec_wait'] = False
        t['data']['spec_accepted_by_owner'] = True
        self.db.update_task(tid, status='DELIVER', data=t['data'])

    def spec_more(self, tid: str) -> None:
        t = self.db.task(tid)
        if not t or not t['data'].get('spec_wait'):
            raise ValueError('task is not waiting on a spec decision')
        t['data']['spec_wait'] = False
        t['data']['spec_extra'] = t['data'].get('spec_extra', 0) + 1
        last = (t['data'].get('spec_reviews') or [{}])[-1]
        self._send_back(t, self._spec_feedback(last.get('unmet', []), {
            'tampering': last.get('tampering'), 'tampering_reason': last.get('tampering_reason', '')}))

    def _deliver(self, t: dict) -> None:
        wt = Path(t['worktree'])
        title = t['prompt'].strip().splitlines()[0][:72]
        git.git(wt, 'reset', '-q', '--soft', t['base_ref'])     # squash the wip snapshots
        spec = t['data'].get('spec_reviews') or []
        triage_notes = t['data'].get('triage_notes') or {}
        spec_note = ((''.join(f'Note: check {k} {"was flaky (passed on rerun)" if v == "FLAKY" else "already failed on the base commit"}.\n'
                              for k, v in triage_notes.items())) +
                     f'Spec review: {len(spec)} round(s)' +
                     (', accepted by owner' if t['data'].get('spec_accepted_by_owner') else ', all criteria met')
                     if spec else 'Spec review: skipped')
        sha = git.commit_all(wt, f'aa: {title}\n\nTask {t["id"]} via {t["lane"]}.\n'
                                 f'Checks:\n{t["data"].get("checks_result", "")}\n{spec_note}')
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
        git.remove_worktree(Path(t['repo']), self.cfg.state_dir / 'base-wt' / t['id'])
        cleanup_quality_worktrees(self.cfg, t)
        self.n.send(f'Done {t["id"]} ({t["lane"]})',
                    f'{title}\n{result}\n{t["data"].get("checks_result", "")}\n{spec_note}\n{stat[-800:]}',
                    tags='white_check_mark')

    # -------------------------------------------------------------------- deep
    def _to_deep(self, t: dict, reason: str) -> None:
        self.db.event('to_deep', t['id'], reason=reason)
        if t['case_id']:
            return
        cid = self.db.create_case(t['id'])
        self.db.update_task(t['id'], status='DEEP', case_id=cid, tier='tough',
                            result=f'deep case {cid}: {reason}')
