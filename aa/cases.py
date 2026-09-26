"""Deep cases: Pro drafts -> Opus x Astra challenge rounds -> Pro GO/CLARIFY -> verify.

Phases (cases.phase):
  NEW          prepare case branch, BRIEF, PRO-TURN-01; notify owner
  WAIT_PRO     poll the case branch for the Pro turn marker file
  CHALLENGE    one challenger turn per step, committed and pushed by the coordinator
  WAIT_OWNER   Pro asked owner questions; waiting for `answer <case> ...`
  VERIFY       fetch Pro's implementation branch and run the required checks
  FIX          local Opus high fixes check failures within the approved design
  DONE / PAUSED / FAILED
Pro works through the ChatGPT GitHub connector; the owner only pastes a one-line
prompt (sent via ntfy) into the case's Pro chat.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from . import checks as checks_mod
from . import git
from .config import Config
from .db import DB
from .notify import Notifier
from .retrieval import bm25_rank
from .tasks import bullet, render
from .workers import LANES, Workers

ACTIVE = ('NEW', 'WAIT_PRO', 'CHALLENGE', 'VERIFY', 'FIX')
CHALLENGER_NAME = {'opus_high': 'opus', 'astra_high': 'astra'}


class CaseFlow:
    def __init__(self, cfg: Config, db: DB, workers: Workers, decider, notifier: Notifier):
        self.cfg, self.db, self.workers, self.decider, self.n = cfg, db, workers, decider, notifier
        self.slug = cfg['case_repo']['slug']
        self.deep = cfg['deep']

    # ------------------------------------------------------------ case repo
    def repo(self) -> Path:
        d = self.cfg.case_repo_dir
        if not (d / '.git').exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            git.git(d.parent, 'clone', '-q', self.cfg['case_repo']['url'], d.name)
        if not git.git(d, 'rev-parse', '--verify', '--quiet', 'HEAD', check=False):
            # Empty remote: create main with the shared protocol.
            (d / 'PROTOCOL.md').write_text((Path(__file__).parent / 'prompts' / 'case_protocol.md').read_text())
            (d / 'README.md').write_text('# GPT-Pro-Escalation\n\nPrivate AgenticArch deep cases. '
                                         'See PROTOCOL.md. One branch per case: `case/<id>`.\n')
            git.git(d, 'checkout', '-q', '-B', 'main')
            git.commit_all(d, 'Initialize AgenticArch case repository')
            git.git(d, 'push', '-q', '-u', 'origin', 'main')
        return d

    def case_wt(self, c: dict) -> Path:
        return self.cfg.state_dir / 'case-wt' / c['id']

    def target_ro(self, c: dict) -> Path:
        return self.cfg.state_dir / 'target-ro' / c['id']

    # ------------------------------------------------------------------ steps
    def step(self, c: dict) -> None:
        handler = {'NEW': self._prepare, 'WAIT_PRO': self._poll_pro, 'CHALLENGE': self._challenge,
                   'VERIFY': self._verify, 'FIX': self._fix}.get(c['phase'])
        if handler:
            handler(c)

    def _prepare(self, c: dict) -> None:
        t = self.db.task(c['task_id'])
        target = Path(t['repo'])
        tslug = git.github_slug(target)
        if not tslug:
            self._fail(c, 'target repository has no GitHub origin; Pro cannot read or implement it')
            return
        # Make the exact base commit readable for Pro (it may exist only locally).
        base_branch = f'aa/base-{c["id"]}'
        git.git(target, 'push', '-q', 'origin', f'{t["base_ref"]}:refs/heads/{base_branch}')
        repo = self.repo()
        git.git(repo, 'fetch', '-q', 'origin')
        wt = self.case_wt(c)
        git.add_worktree(repo, wt, c['branch'], 'origin/main')
        cdir = wt / 'cases' / c['id']
        (cdir / 'turns').mkdir(parents=True, exist_ok=True)
        tri = t['data'].get('triage') or {}
        paths = self._context_paths(t, target, tri)
        (cdir / 'BRIEF.md').write_text(render(
            'brief.md', case_id=c['id'], task_id=t['id'], prompt=t['prompt'],
            target_slug=tslug, base_commit=t['base_ref'], base_branch=base_branch,
            summary=tri.get('summary') or '(triage unavailable)',
            acceptance=bullet(tri.get('acceptance_criteria')), risks=bullet(tri.get('risks')),
            categories=', '.join(tri.get('pro_categories') or []) or 'none flagged',
            paths=bullet(paths), checks=bullet([f'{k}: `{v}`' for k, v in
                                                (t['data'].get('checks') or {}).items()], '- (none)'),
            history=bullet([f'{a["lane"]}: {"ok" if a["ok"] else "failed"} — {a["summary"][-300:]}'
                            for a in t['data'].get('attempts', [])], '- (no local attempts)'),
            last_failure=t['data'].get('last_failure') or '(none)'))
        c['data'].update(target_slug=tslug, base_branch=base_branch)
        self.db.update_case(c['id'], data=c['data'])
        self._request_pro(c, 'pro_draft.md', first=True)

    def _context_paths(self, t: dict, target: Path, tri: dict) -> list[str]:
        """BRIEF reading list: triage's relevant paths first, then BM25 over file contents
        (measured better than SemIf ranking and path keywords, see aa/retrieval.py)."""
        tracked = git.git(target, 'ls-files', check=False).splitlines()
        pinned = [p for p in tri.get('relevant_paths') or [] if p in tracked][:12]
        rest = [p for p in bm25_rank(t['prompt'], target, tracked[:5000], 12) if p not in pinned]
        return (pinned + rest)[:12]

    def _request_pro(self, c: dict, template: str, *, first: bool = False, **extra: object) -> None:
        nn = c['pro_turn'] + 1
        marker = f'pro-{nn:02d}.md'
        wt = self.case_wt(c)
        path = f'cases/{c["id"]}'
        t = self.db.task(c['task_id'])
        (wt / path / f'PRO-TURN-{nn:02d}.md').write_text(render(
            template, nn=f'{nn:02d}', case_id=c['id'], case_slug=self.slug, case_branch=c['branch'],
            case_path=path, target_slug=c['data']['target_slug'], base_commit=t['base_ref'],
            marker=marker, impl_branch=f'aa/case-{c["id"]}', **extra))
        git.commit_all(wt, f'aa {c["id"]}: request Pro turn {nn:02d}')
        git.git(wt, 'push', '-q', '-u', 'origin', c['branch'])
        c['data']['expect_marker'] = marker
        self.db.update_case(c['id'], pro_turn=nn, phase='WAIT_PRO', data=c['data'])
        line = (f'AgenticArch case {c["id"]}: in GitHub repo {self.slug}, branch {c["branch"]}, '
                f'read {path}/PRO-TURN-{nn:02d}.md and do exactly what it says.')
        c['data']['pro_prompt'] = line
        self.db.update_case(c['id'], data=c['data'])
        where = ('Start a NEW GPT-6 Pro chat (GitHub connector on) and name it '
                 f'"AA {c["id"]}".' if first else f'Continue in the SAME Pro chat "AA {c["id"]}".')
        self.n.send(f'Pro turn {nn:02d}: {c["id"]}', f'{where}\n\nPaste:\n{line}', priority=4,
                    tags='robot')

    # ---------------------------------------------------------------- Pro wait
    def _poll_pro(self, c: dict) -> None:
        wt = self.case_wt(c)
        git.git(wt, 'fetch', '-q', 'origin', c['branch'])
        rel = f'cases/{c["id"]}/turns/{c["data"]["expect_marker"]}'
        text = git.git(wt, 'show', f'origin/{c["branch"]}:{rel}', check=False)
        if f'TURN-COMPLETE: {c["id"]}/{c["pro_turn"]:02d}' not in text:
            return
        git.git(wt, 'merge', '-q', '--ff-only', f'origin/{c["branch"]}')
        self.db.event('pro_turn_complete', c['task_id'], c['id'], turn=c['pro_turn'])
        if c['pro_turn'] == 1:
            if not (wt / 'cases' / c['id'] / 'SOLUTION.md').exists():
                self._fail(c, 'Pro turn completed without SOLUTION.md')
                return
            self._start_cycle(c)
            return
        decision = _field(text, 'DECISION')
        reviews = c['pro_reviews'] + 1
        self.db.update_case(c['id'], pro_reviews=reviews)
        if decision == 'GO':
            branch, sha = _field(text, 'TARGET-BRANCH'), _field(text, 'TARGET-COMMIT')
            if not branch or not sha:
                self._fail(c, 'GO without TARGET-BRANCH/TARGET-COMMIT')
                return
            c['data'].update(impl_branch=branch, impl_commit=sha, fixes=0)
            self.db.update_case(c['id'], phase='VERIFY', data=c['data'])
            return
        questions = _section(text, 'Owner questions')
        if questions:
            c['data']['owner_questions'] = questions
            self.db.update_case(c['id'], phase='WAIT_OWNER', data=c['data'])
            self.n.send(f'Owner decision: {c["id"]}', questions[:3000] +
                        f'\n\nReply on the workstation: aa answer "answer {c["id"]} <your answer>"',
                        priority=4, tags='question')
            return
        if reviews >= self.deep['max_pro_reviews'] + c['data'].get('extra_reviews', 0):
            self.db.update_case(c['id'], phase='PAUSED')
            self.n.send(f'Paused: {c["id"]}',
                        f'{reviews} Pro reviews without GO. Read the case branch {c["branch"]}; then '
                        f'aa answer "answer {c["id"]} <guidance>" or "resume {c["id"]}".',
                        choices=[('Resume', f'resume {c["id"]}')], priority=4, tags='pause_button')
            return
        self._start_cycle(c)

    # --------------------------------------------------------------- challenge
    def _start_cycle(self, c: dict) -> None:
        c = self.db.case(c['id'])
        self.db.update_case(c['id'], phase='CHALLENGE', cycle=c['cycle'] + 1, round=1)

    def _challenge(self, c: dict) -> None:
        wt, target = self.case_wt(c), self.target_ro(c)
        t = self.db.task(c['task_id'])
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            git.git(Path(t['repo']), 'worktree', 'add', '--detach', str(target), t['base_ref'])
        cdir = wt / 'cases' / c['id']
        challengers = list(self.deep['challengers'])
        rounds = int(self.deep['challenge_rounds'])
        prefix = f'cycle{c["cycle"]}-r{c["round"]}'
        todo = [l for l in challengers
                if not (cdir / 'turns' / f'{prefix}-{CHALLENGER_NAME[l]}.md').exists()]
        if not todo:
            self._end_round(c, cdir, prefix, challengers, rounds)
            return
        lane_name = todo[0]
        me = CHALLENGER_NAME[lane_name]
        partner = next(CHALLENGER_NAME[l] for l in challengers if l != lane_name)
        turn_file = f'{prefix}-{me}.md'
        prompt = render('challenger.md', role={'opus': 'Claude Opus 5.5', 'astra': 'GPT-6 Astra'}[me],
                        case_id=c['id'], round=c['round'], rounds=rounds, cycle=c['cycle'],
                        partner=partner, case_dir=cdir, target_dir=target, turn_file=turn_file)
        res = self.workers.execute(LANES[lane_name], prompt, wt, extra_dirs=(target,),
                                   log_name=f'{c["id"]}-{prefix}-{me}')
        # Enforce write scope: only this case directory; the target snapshot stays pristine.
        allowed = f'cases/{c["id"]}/'
        outside = [p for p in git.changed_paths(wt) if not p.startswith(allowed)]
        for p in outside:
            git.git(wt, 'checkout', '--', p, check=False)
            git.git(wt, 'clean', '-qf', '--', p, check=False)
        if git.changed_paths(target):
            git.discard(target)
            outside.append('<target repository>')
        if outside:
            self.db.event('scope_violation', c['task_id'], c['id'], who=me, paths=outside[:20])
        if not (cdir / 'turns' / turn_file).exists():
            (cdir / 'turns' / turn_file).write_text(
                f'# {me} turn missing\n\nWorker ok={res.ok} error={res.error[:500]}\n\n'
                f'Final message:\n{res.text[-2000:]}\n\nVERDICT: REVISE\n')
        git.commit_all(wt, f'aa {c["id"]}: {prefix} {me}')
        git.git(wt, 'push', '-q', 'origin', c['branch'])

    def _end_round(self, c: dict, cdir: Path, prefix: str, challengers: list[str], rounds: int) -> None:
        verdicts = {CHALLENGER_NAME[l]: _verdict((cdir / 'turns' / f'{prefix}-{CHALLENGER_NAME[l]}.md').read_text())
                    for l in challengers}
        c['data'].setdefault('verdicts', {})[prefix] = verdicts
        self.db.update_case(c['id'], data=c['data'])
        if all(v == 'AGREE' for v in verdicts.values()) or c['round'] >= rounds:
            answers = ''
            ans_file = cdir / 'OWNER-ANSWERS.md'
            if ans_file.exists():
                answers = f'\nThe owner answered questions in `cases/{c["id"]}/OWNER-ANSWERS.md`; respect them.\n'
            c['data']['awaiting'] = 'review'
            self.db.update_case(c['id'], data=c['data'])
            self._request_pro(self.db.case(c['id']), 'pro_review.md', rounds_done=c['round'],
                              verdicts=', '.join(f'{k}: {v}' for k, v in verdicts.items()),
                              owner_answers=answers)
        else:
            self.db.update_case(c['id'], round=c['round'] + 1)

    # ------------------------------------------------------------- owner input
    def answer(self, cid: str, text: str) -> None:
        c = self.db.case(cid)
        if not c:
            raise ValueError('unknown case')
        wt = self.case_wt(c)
        f = wt / 'cases' / cid / 'OWNER-ANSWERS.md'
        prev = f.read_text() if f.exists() else '# Owner answers\n'
        f.write_text(prev + f'\n## After Pro turn {c["pro_turn"]:02d}\n\n{text.strip()}\n')
        git.commit_all(wt, f'aa {cid}: owner answer')
        git.git(wt, 'push', '-q', 'origin', c['branch'])
        if c['phase'] in ('WAIT_OWNER', 'PAUSED'):
            self.resume(cid)

    def resume(self, cid: str) -> None:
        c = self.db.case(cid)
        if c['phase'] == 'PAUSED':
            c['data']['extra_reviews'] = c['data'].get('extra_reviews', 0) + 1
            self.db.update_case(cid, data=c['data'])
        if c['phase'] in ('WAIT_OWNER', 'PAUSED'):
            self._start_cycle(c)

    # ------------------------------------------------------------ verification
    def _impl_wt(self, c: dict) -> Path:
        return self.cfg.worktrees / f'{c["id"]}-impl'

    def _verify(self, c: dict) -> None:
        t = self.db.task(c['task_id'])
        target, branch = Path(t['repo']), c['data']['impl_branch']
        git.git(target, 'fetch', '-q', 'origin', branch)
        fresh = c['data'].get('fixes', 0) == 0   # first verification after a Pro GO
        declared = c['data']['impl_commit']
        tip = git.git(target, 'rev-parse', f'origin/{branch}')
        if fresh and not (len(declared) >= 7 and tip.startswith(declared)):
            # Only the exact commit Pro declared with GO may be verified and delivered.
            if not _is_ancestor(target, declared, f'origin/{branch}'):
                self._fail(c, f'Pro implementation commit {declared} not on origin/{branch}')
            else:
                self._back_to_pro(c, f'origin/{branch} is at {tip[:12]}, not at the declared TARGET-COMMIT '
                                     f'{declared[:12]}. Declare the final commit of the branch.')
            return
        wt = self._impl_wt(c)
        if not wt.exists():
            git.git(target, 'branch', '-f', branch, f'origin/{branch}', check=False)
            git.add_worktree(target, wt, branch, f'origin/{branch}')
        elif fresh:
            git.git(wt, 'reset', '-q', '--hard', f'origin/{branch}')
        results = checks_mod.run(t['data'].get('checks') or {}, wt)
        git.discard(wt)                      # drop artefacts produced by the checks
        c['data']['checks_result'] = checks_mod.summary(results)
        if all(r.ok for r in results):
            # Must succeed before completion: a failed push raises, the daemon retries and then
            # pauses the case, instead of reporting success for fixes that never reached the remote.
            git.git(wt, 'push', '-q', 'origin', f'HEAD:{branch}')
            self.db.update_case(c['id'], phase='DONE', data=c['data'])
            self.db.update_task(t['id'], status='DONE',
                                result=f'deep case {c["id"]}: branch {branch} verified')
            self.db.decision_outcome(t['id'], 'tier', 'deep_done')
            git.remove_worktree(target, wt)
            git.remove_worktree(target, self.target_ro(c))
            self.n.send(f'Done (deep) {c["id"]}', f'{t["prompt"][:200]}\nBranch {branch}\n'
                        f'{c["data"]["checks_result"]}', tags='white_check_mark')
            return
        c['data']['last_failure'] = checks_mod.failure_report(results)
        self.db.update_case(c['id'], phase='FIX', data=c['data'])

    def _fix(self, c: dict) -> None:
        wt = self._impl_wt(c)
        fixes = c['data'].get('fixes', 0)
        if fixes >= int(self.cfg['retry']['max_passes_per_lane']):
            self._back_to_pro(c, 'Local fixes did not make the checks pass.')
            return
        sol = self.case_wt(c) / 'cases' / c['id'] / 'SOLUTION.md'
        prompt = render('fix.md', worktree=wt, branch=c['data']['impl_branch'], solution=sol,
                        failures=c['data']['last_failure'])
        res = self.workers.execute(LANES['opus_high'], prompt, wt, extra_dirs=(sol.parent,),
                                   log_name=f'{c["id"]}-fix{fixes + 1}')
        c['data']['fixes'] = fixes + 1
        issue = next((ln for ln in res.text.splitlines() if ln.startswith('DESIGN_ISSUE:')), None)
        if issue:
            git.discard(wt)
            self.db.update_case(c['id'], data=c['data'])
            self._back_to_pro(c, issue)
            return
        git.commit_all(wt, f'aa {c["id"]}: local fix {fixes + 1} (Opus high)')
        self.db.update_case(c['id'], phase='VERIFY', data=c['data'])

    def _back_to_pro(self, c: dict, reason: str) -> None:
        self.db.event('back_to_pro', c['task_id'], c['id'], reason=reason[:500])
        wt = self._impl_wt(c)
        if wt.exists():                       # Pro must see the local fixes: a failed push raises
            git.git(wt, 'push', '-q', 'origin', f'HEAD:{c["data"]["impl_branch"]}')
        c['data']['awaiting'] = 'review'
        self.db.update_case(c['id'], data=c['data'])
        note = (f'\n**Post-GO verification failed.** {reason}\nFailing checks on '
                f'`{c["data"]["impl_branch"]}`:\n\n{c["data"].get("last_failure", "")[:6000]}\n\n'
                f'Fix the design and/or implementation on the same branch, then decide again.\n')
        self._request_pro(self.db.case(c['id']), 'pro_review.md', rounds_done=0,
                          verdicts='(post-GO verification)', owner_answers=note)

    def _fail(self, c: dict, reason: str) -> None:
        self.db.update_case(c['id'], phase='FAILED')
        self.db.update_task(c['task_id'], status='FAILED', result=f'case {c["id"]}: {reason}')
        self.n.send(f'Case failed {c["id"]}', reason, priority=4, tags='x')


def _field(text: str, name: str) -> str | None:
    m = re.search(rf'^\s*\**{re.escape(name)}\**\s*:\s*\**\s*([^\s*|]+)', text, re.M)
    return m.group(1).strip() if m else None


def _section(text: str, heading: str) -> str:
    m = re.search(rf'^#+\s*{re.escape(heading)}\s*$(.*?)(?=^#+\s|\Z)', text, re.M | re.S | re.I)
    body = m.group(1).strip() if m else ''
    return '' if body.lower() in ('', 'none', '- none', 'n/a') else body


def _verdict(text: str) -> str:
    found = re.findall(r'VERDICT:\s*(AGREE|REVISE)', text)
    return found[-1] if found else 'REVISE'


def _is_ancestor(repo: Path, a: str, b: str) -> bool:
    return subprocess.run(['git', 'merge-base', '--is-ancestor', a, b], cwd=str(repo),
                          capture_output=True).returncode == 0
