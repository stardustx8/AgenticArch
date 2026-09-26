"""Required checks per target repo: `.agenticarch.toml` or autodetect + one-time owner OK.

`.agenticarch.toml` in the target repo:

    [checks]
    test = "python -m pytest -q"
    lint = "ruff check ."

Checks are executed by the coordinator (never by the worker's claim) on the exact
worktree snapshot; every non-zero exit blocks completion.
"""
from __future__ import annotations

import json
import os
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path


def from_file(repo: Path) -> dict[str, str] | None:
    f = repo / '.agenticarch.toml'
    if not f.exists():
        return None
    with open(f, 'rb') as fh:
        checks = tomllib.load(fh).get('checks', {})
    if not isinstance(checks, dict) or not all(isinstance(v, str) and v.strip() for v in checks.values()):
        raise ValueError('.agenticarch.toml [checks] must map names to shell commands')
    return dict(checks)


def autodetect(repo: Path) -> dict[str, str]:
    checks: dict[str, str] = {}
    pj = repo / 'package.json'
    if pj.exists():
        try:
            scripts = json.loads(pj.read_text()).get('scripts', {})
        except ValueError:
            scripts = {}
        runner = 'pnpm' if (repo / 'pnpm-lock.yaml').exists() else (
            'yarn' if (repo / 'yarn.lock').exists() else 'npm')
        for name in ('lint', 'typecheck', 'build', 'test'):
            if name in scripts and 'no test specified' not in scripts[name]:
                checks[name] = f'{runner} run {name}' if name != 'test' else f'{runner} test'
    if (repo / 'pyproject.toml').exists() or (repo / 'setup.py').exists() or any(repo.glob('test*/**/test_*.py')):
        txt = (repo / 'pyproject.toml').read_text() if (repo / 'pyproject.toml').exists() else ''
        if 'pytest' in txt or (repo / 'pytest.ini').exists() or (repo / 'conftest.py').exists():
            checks['pytest'] = 'python -m pytest -q'
        elif (repo / 'tests').is_dir():
            checks['unittest'] = 'python -m unittest discover -s tests -q'
        if 'ruff' in txt:
            checks['ruff'] = 'ruff check .'
    if (repo / 'Cargo.toml').exists():
        checks['cargo_test'] = 'cargo test --quiet'
    if (repo / 'go.mod').exists():
        checks['go_test'] = 'go test ./...'
    if not checks and (repo / 'Makefile').exists() and 'test:' in (repo / 'Makefile').read_text():
        checks['make_test'] = 'make test'
    return checks


@dataclass
class CheckRun:
    name: str
    command: str
    exit_code: int
    output: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def run(checks: dict[str, str], cwd: Path, timeout: int = 1800) -> list[CheckRun]:
    results = []
    for name, cmd in checks.items():
        try:
            p = subprocess.run(cmd, shell=True, cwd=str(cwd), capture_output=True, text=True,
                               timeout=timeout, stdin=subprocess.DEVNULL,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
            out = (p.stdout + p.stderr)[-6000:]
            results.append(CheckRun(name, cmd, p.returncode, out))
        except subprocess.TimeoutExpired:
            results.append(CheckRun(name, cmd, 124, f'timeout after {timeout}s'))
    return results


def summary(results: list[CheckRun]) -> str:
    return '\n'.join(f'- {r.name} (`{r.command}`): {"PASS" if r.ok else f"FAIL exit {r.exit_code}"}'
                     for r in results) or '- (no checks)'


def failure_report(results: list[CheckRun]) -> str:
    return '\n\n'.join(f'### {r.name}: `{r.command}` exit {r.exit_code}\n```\n{r.output[-3000:]}\n```'
                       for r in results if not r.ok)
