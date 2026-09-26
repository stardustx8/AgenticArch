#!/usr/bin/env python3
"""Import generated lab tasks (JSON lines) and keep only VALID ones.

A task is valid when, in a clean copy of its repository:
  1. the existing tests pass on the original code,
  2. the hidden tests fail on the original code,
  3. existing + hidden tests pass with the reference solution applied.
Valid tasks are written to eval/lab/tasks/<id>/ {task.json, repo/, hidden/, reference/}.
Usage: python3 eval/lab/import_tasks.py raw1.json [raw2.json ...]   (claude -p --output-format json files)
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

LAB = Path(__file__).resolve().parent
TASKS = LAB / 'tasks'


def write_tree(root: Path, files: dict) -> None:
    for rel, content in files.items():
        rel = rel.lstrip('/')
        if '..' in Path(rel).parts:
            raise ValueError(f'unsafe path {rel}')
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)


def tests_pass(root: Path, pattern: str = 'test*.py') -> tuple[bool, str]:
    if not (root / 'tests').is_dir():
        return False, 'no tests dir'
    p = subprocess.run(['python3', '-m', 'unittest', 'discover', '-s', 'tests', '-t', '.', '-p', pattern],
                       cwd=root, capture_output=True, text=True, timeout=120)
    return p.returncode == 0, (p.stdout + p.stderr)[-800:]


def validate(task: dict) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_tree(root, task['files'])
        (root / 'tests' / '__init__.py').touch()
        ok, out = tests_pass(root)
        if not ok:
            return 'existing tests fail on the original code: ' + out[-200:]
        write_tree(root, task['hidden_tests'])
        ok, _ = tests_pass(root, 'test_hidden_*.py')
        if ok:
            return 'hidden tests already pass on the original code'
        write_tree(root, task['reference'])
        ok, out = tests_pass(root)
        if not ok:
            return 'reference does not pass existing + hidden tests: ' + out[-300:]
    return ''


def main() -> int:
    TASKS.mkdir(parents=True, exist_ok=True)
    kept = rejected = 0
    for raw in sys.argv[1:]:
        text = json.load(open(raw))['result']
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith('{'):
                continue
            try:
                task = json.loads(line)
                reason = validate(task)
            except (ValueError, KeyError, subprocess.TimeoutExpired) as exc:
                reason = f'unreadable: {exc}'
                task = task if isinstance(task, dict) else {'id': '?'}
            if reason:
                rejected += 1
                print(f'REJECT {task.get("id")}: {reason}')
                continue
            d = TASKS / task['id']
            shutil.rmtree(d, ignore_errors=True)
            write_tree(d / 'repo', task['files'])
            (d / 'repo' / 'tests' / '__init__.py').touch()
            write_tree(d / 'hidden', task['hidden_tests'])
            write_tree(d / 'reference', task['reference'])
            (d / 'task.json').write_text(json.dumps({k: task.get(k, 'none') for k in ('id', 'tier_hint', 'prompt', 'trap')}, indent=1))
            kept += 1
    print(f'kept {kept}, rejected {rejected}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
