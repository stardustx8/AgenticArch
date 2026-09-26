"""Thin git helpers (subprocess; raises on failure)."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

# Commit identity for coordinator commits (set from config by the daemon).
IDENTITY = {'name': 'AgenticArch aa', 'email': 'aa@agenticarch.invalid'}


class GitError(RuntimeError):
    pass


def git(cwd: Path | str, *args: str, check: bool = True, timeout: int = 300,
        strip: bool = True) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME=IDENTITY['name'], GIT_AUTHOR_EMAIL=IDENTITY['email'],
               GIT_COMMITTER_NAME=IDENTITY['name'], GIT_COMMITTER_EMAIL=IDENTITY['email'],
               GIT_TERMINAL_PROMPT='0')
    p = subprocess.run(['git', *args], cwd=str(cwd), capture_output=True, text=True,
                       timeout=timeout, stdin=subprocess.DEVNULL, env=env)
    if check and p.returncode != 0:
        raise GitError(f'git {" ".join(args)} failed in {cwd}: {p.stderr.strip()[-800:]}')
    return p.stdout.strip() if strip else p.stdout


def toplevel(path: Path) -> Path:
    return Path(git(path, 'rev-parse', '--show-toplevel'))


def head(cwd: Path) -> str:
    return git(cwd, 'rev-parse', 'HEAD')


def github_slug(repo: Path) -> str | None:
    url = git(repo, 'remote', 'get-url', 'origin', check=False)
    m = re.search(r'github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$', url)
    return m.group(1) if m else None


def add_worktree(repo: Path, path: Path, branch: str, base: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    exists = git(repo, 'rev-parse', '--verify', '--quiet', f'refs/heads/{branch}', check=False)
    if exists:
        git(repo, 'worktree', 'add', str(path), branch)
    else:
        git(repo, 'worktree', 'add', '-b', branch, str(path), base)


def remove_worktree(repo: Path, path: Path) -> None:
    if path.exists():
        git(repo, 'worktree', 'remove', '--force', str(path), check=False)


def changed_paths(cwd: Path) -> list[str]:
    """Tracked and untracked changes relative to HEAD (paths as git prints them)."""
    # No strip(): the first line's leading status column is significant.
    out = git(cwd, 'status', '--porcelain=v1', '-uall', strip=False)
    paths = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        p = line[3:]
        if ' -> ' in p:
            p = p.split(' -> ', 1)[1]
        paths.append(p.strip('"'))
    return paths


# Never committed by the coordinator, even when a repo lacks a .gitignore for them.
ARTEFACTS = ('__pycache__', '*.pyc', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'node_modules',
             '.venv', '.tox', '.coverage', '.DS_Store')


def commit_all(cwd: Path, message: str) -> str | None:
    if not changed_paths(cwd):
        return None
    git(cwd, 'add', '-A', '--', '.', *(f':(exclude,glob)**/{a}' for a in ARTEFACTS),
        *(f':(exclude,glob)**/{a}/**' for a in ARTEFACTS if '*' not in a))
    if not git(cwd, 'diff', '--cached', '--name-only'):
        return None
    git(cwd, 'commit', '-q', '-m', message)
    return head(cwd)


def discard(cwd: Path) -> None:
    git(cwd, 'reset', '-q', '--hard')
    git(cwd, 'clean', '-qfd')


def diffstat(cwd: Path, base: str) -> str:
    return git(cwd, 'diff', '--stat', f'{base}..HEAD', check=False)[-3000:]
