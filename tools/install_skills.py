#!/usr/bin/env python3
"""Install the two shipped skill revisions; preview by default, local I/O only.

Apply creates full backups first and replaces only shipped files. Unshipped
helpers remain untouched. Intended for one local operator, not concurrent
administration of skill trees. Live client reload/qualification is separate.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import uuid

NAMES = ('agenticarch', 'prepare-sol-pro-architecture-review', 'fable-adversarial-review')
ROOT = Path(__file__).resolve().parents[1]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def plain_path(path: Path) -> Path:
    """Reject links at every existing path component, not just the leaf."""
    path = path.expanduser().absolute()
    for component in reversed((path, *path.parents)):
        if component.is_symlink():
            raise ValueError(f'Symlink paths are not supported: {component}')
        if component.exists() and not (component.is_dir() or component.is_file()):
            raise ValueError(f'Special path is not supported: {component}')
    return path


def plain_tree(path: Path) -> None:
    plain_path(path)
    if not path.exists():
        return
    if not path.is_dir():
        raise ValueError(f'Expected a directory: {path}')
    for current, dirs, files in os.walk(path, followlinks=False):
        for name in (*dirs, *files):
            item = Path(current) / name
            mode = item.lstat().st_mode
            if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError(f'Link or special file is not supported: {item}')


def overlaps(a: Path, b: Path) -> bool:
    return a == b or a in b.parents or b in a.parents


def atomic_write(path: Path, content: bytes, mode: int = 0o644) -> None:
    plain_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.agenticarch-install-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def plan_install(source_root: Path, target_root: Path) -> list[dict]:
    source_root, target_root = plain_path(source_root), plain_path(target_root)
    if overlaps(source_root, target_root):
        raise ValueError('Source and target skill roots must not overlap')
    if target_root.exists() and not target_root.is_dir():
        raise ValueError('Target root must be a directory')
    plan = []
    for name in NAMES:
        source, destination = source_root / name, target_root / name
        plain_tree(source)
        plain_tree(destination)
        if not (source / 'SKILL.md').is_file():
            raise ValueError(f'Missing source skill: {name}')
        for item in sorted(source.rglob('*')):
            if not item.is_file():
                continue
            relative = item.relative_to(source_root)
            target = target_root / relative
            plain_path(target)
            if target.exists() and not target.is_file():
                raise ValueError(f'File target is not a regular file: {target}')
            old = target.read_bytes() if target.exists() else None
            new = item.read_bytes()
            if old == new:
                continue
            plan.append({'path': str(relative), 'action': 'UPDATE' if old is not None else 'CREATE',
                         'before': digest(old) if old is not None else None,
                         'after': digest(new), 'old_bytes': old, 'new_bytes': new,
                         'old_mode': stat.S_IMODE(target.stat().st_mode) if target.exists() else 0o644})
    return plan


def install(source_root: Path, target_root: Path, *, apply: bool = False,
            backup_root: Path | None = None) -> dict:
    source_root, target_root = plain_path(source_root), plain_path(target_root)
    plan = plan_install(source_root, target_root)
    public_plan = [{k: v for k, v in row.items() if k not in {'old_bytes', 'new_bytes'}} for row in plan]
    report = {'mode': 'APPLY' if apply else 'DRY_RUN', 'target_root': str(target_root),
              'changes': public_plan, 'backup': None}
    if not apply or not plan:
        return report
    if backup_root is None:
        raise ValueError('--backup-root is required with --apply')
    backup_root = plain_path(backup_root)
    if overlaps(backup_root, source_root) or overlaps(backup_root, target_root):
        raise ValueError('Backup root must be outside source and target skill trees')
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    backup = backup_root / stamp
    backup.mkdir(mode=0o700)
    report['backup'] = str(backup)
    for name in NAMES:
        old_tree = target_root / name
        plain_tree(old_tree)
        if old_tree.exists():
            shutil.copytree(old_tree, backup / name)
    manifest = {'schema_version': 1, 'target_root': str(target_root),
                'changes': public_plan, 'status': 'PREPARED'}
    atomic_write(backup / 'manifest.json', (json.dumps(manifest, indent=2)+'\n').encode(), 0o600)
    # Refuse stale plans before mutating any file.
    for row in plan:
        path = target_root / row['path']
        current = path.read_bytes() if path.exists() else None
        if current != row['old_bytes']:
            raise ValueError(f'Installed file changed after planning: {path}; backup at {backup}')
    changed = []
    try:
        for row in plan:
            path = target_root / row['path']
            atomic_write(path, row['new_bytes'], row['old_mode'])
            changed.append(row)
        for row in plan:
            if digest((target_root / row['path']).read_bytes()) != row['after']:
                raise ValueError(f'Installed hash mismatch: {row["path"]}')
        manifest['status'] = 'APPLIED'
        atomic_write(backup / 'manifest.json', (json.dumps(manifest, indent=2)+'\n').encode(), 0o600)
    except Exception:
        # Best-effort rollback of our own writes only; preserve unrelated files.
        for row in reversed(changed):
            path = target_root / row['path']
            if row['old_bytes'] is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, row['old_bytes'], row['old_mode'])
        raise
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-root', required=True, type=Path)
    parser.add_argument('--backup-root', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    try:
        result = install(ROOT / 'skills', args.target_root, apply=args.apply, backup_root=args.backup_root)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Install stopped: {exc}\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
