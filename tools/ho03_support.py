"""Evaluator-side HO-03 bounds and receipts. No provider calls or completion approvals."""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
from tools.ho02_support import atomic, digest


def safe_bytes(root, name):
    root = Path(root).resolve()
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts:
        return None
    target = root
    for part in relative.parts:
        target = target / part
        if target.is_symlink():
            return None
    try:
        return target.read_bytes() if target.is_file() else None
    except OSError:
        return None


def protected_hashes(root, names):
    result = {}
    for name in names:
        value = safe_bytes(root, name)
        result[name] = hashlib.sha256(value).hexdigest() if value is not None else None
    return result


def preservation(root, originals, stage_start=None):
    actual = protected_hashes(root, originals)
    baseline = {p: hashlib.sha256(v.encode()).hexdigest() for p, v in originals.items()}
    before = baseline if stage_start is None else stage_start
    if set(before) != set(baseline):
        raise ValueError('incomplete protected stage-start snapshot')
    return {'protected_preserved': actual == baseline,
            'protected_changed_this_stage': [p for p in baseline if actual[p] != before[p] and actual[p] != baseline[p]],
            'protected_files_changed': [p for p in baseline if actual[p] != before[p]],
            'inherited_protected_damage': [p for p in baseline if before[p] != baseline[p]]}


def deadline(progress, seconds, now=None):
    """A resumed attempt keeps its original wall deadline, including downtime."""
    now = time.time() if now is None else now
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds <= 0:
        raise ValueError('positive finite deadline budget required')
    if 'deadline_at' not in progress:
        if 'started_at' in progress:
            raise ValueError('partial deadline receipt')
        progress.update(started_at=now, deadline_at=now + seconds, timeout_s=seconds)
    if progress.get('timeout_s') != seconds or not all(
            type(progress.get(k)) in (int, float) and math.isfinite(progress[k]) for k in ('started_at', 'deadline_at')):
        raise ValueError('changed or corrupt deadline receipt')
    if progress['deadline_at'] != progress['started_at'] + seconds or now < progress['started_at']:
        raise ValueError('clock moved backwards or deadline changed')
    return max(0, progress['deadline_at'] - now)


def owner_resolution(task, check_record):
    """Never turn missing triage into approval of unrelated check settings."""
    vote = (task['data'].get('tier_votes') or {}).get('codex')
    if vote in ('routine', 'bounded', 'medium_tough', 'tough'):
        return ('tier', vote)
    if task.get('tier') in ('routine', 'bounded', 'medium_tough', 'tough') and check_record and not check_record.get('confirmed'):
        return ('checks', 'ok')
    return ('handback', 'tier unresolved; an explicit owner tier or new triage is required')


def handoff(repo, task, out, max_bytes=64 * 1024 * 1024):
    """Package tracked and regular untracked work without calling GitHub or following links.

    This is an offline handoff-mechanics score, not a completed Pro round, and
    complete bytes do not imply semantic sufficiency. All outputs remain private.
    """
    repo, out = Path(repo).resolve(), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=repo)
    names = sorted(set(git('ls-files', '-co', '--exclude-standard', '-z').decode().split('\0')) - {''})
    files, omitted, total = {}, [], 0
    for name in names:
        value = safe_bytes(repo, name)
        if value is None or len(value) > 8 * 1024 * 1024 or total + len(value) > max_bytes:
            omitted.append(name)
            continue
        dest = out / 'snapshot' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(value)
        files[name] = hashlib.sha256(value).hexdigest()
        total += len(value)
    template = (Path(__file__).resolve().parents[1] / 'aa/prompts/ho03_handoff.md').read_text()
    (out / 'REQUEST.md').write_text(template.format(request=task['prompt']))
    atomic(out / 'task.json', {k: v for k, v in task.items() if k not in ('repo', 'worktree')})
    (out / 'working.diff').write_bytes(git('diff', '--binary', 'HEAD'))
    (out / 'git-status.txt').write_bytes(git('status', '--porcelain=v1'))
    manifest = {'schema_version': 1, 'status': 'AWAITING_PRO', 'awaiting_response': True,
                'completion': False, 'base_sha': git('rev-parse', 'HEAD').decode().strip(),
                'files': files, 'omitted': omitted, 'mechanically_complete': bool(files) and not omitted,
                'semantic_review': 'required', 'transport': 'private local package; not published'}
    manifest['package_files'] = {str(p.relative_to(out)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in out.rglob('*') if p.is_file()}
    atomic(out / 'manifest.json', manifest)
    return manifest


def verify_handoff(out):
    out = Path(out)
    m = json.loads((out / 'manifest.json').read_text())
    for name, expected in m['package_files'].items():
        value = safe_bytes(out, name)
        if value is None or hashlib.sha256(value).hexdigest() != expected:
            raise ValueError('handoff content changed')
    required = {'REQUEST.md', 'task.json', 'working.diff', 'git-status.txt'}
    if not required.issubset(m['package_files']) or m['status'] != 'AWAITING_PRO' or m['completion'] is not False or m['awaiting_response'] is not True:
        raise ValueError('handoff missing explicit awaiting/noncompletion contract')
    return m['mechanically_complete'] is True and bool(m['files']) and not m['omitted']
