"""Subscription-only worker execution through the native CLIs.

Luna/Astra run as `codex exec` (ChatGPT login); Opus runs as `claude -p`
(Claude Max login). API-key variables are removed from the child environment
and the auth mode is verified before every dispatch, so a job can never fall
back to API billing. Claude's reported `modelUsage` must contain the requested
model or the job is treated as failed (no silent model substitution).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .config import Config


@dataclass(frozen=True)
class Lane:
    name: str
    cli: str      # codex|claude
    model: str
    effort: str
    tier: int


LANES: dict[str, Lane] = {l.name: l for l in (
    Lane('luna_low', 'codex', 'gpt-6-luna', 'low', 0),
    Lane('luna_high', 'codex', 'gpt-6-luna', 'high', 1),
    Lane('astra_high', 'codex', 'gpt-6-astra', 'high', 2),
    Lane('opus_medium', 'claude', 'claude-opus-5-5', 'medium', 2),
    Lane('opus_high', 'claude', 'claude-opus-5-5', 'high', 2),
)}

# Removed from every child process: any of these could switch a CLI to API billing
# or to another provider/endpoint.
SCRUB = ('OPENAI_API_KEY', 'OPENAI_BASE_URL', 'CODEX_API_KEY', 'ANTHROPIC_API_KEY',
         'ANTHROPIC_AUTH_TOKEN', 'ANTHROPIC_BASE_URL', 'CLAUDE_CODE_USE_BEDROCK',
         'CLAUDE_CODE_USE_VERTEX', 'CLAUDE_CODE_OAUTH_TOKEN', 'AWS_BEARER_TOKEN_BEDROCK')


AUTH_FAILURE = re.compile(r'401 Unauthorized|Incorrect API key|invalid[_ ]api[_ ]key|'
                          r'authentication_error|not logged in|please (?:re-?)?log ?in', re.I)


class BillingError(RuntimeError):
    """The subscription path could not be verified; never dispatch."""


@dataclass
class Result:
    ok: bool
    text: str                      # final agent message
    structured: dict | None = None
    model_seen: list[str] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    seconds: float = 0.0
    error: str = ''


def child_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items()
           if k not in SCRUB and not k.startswith(('CLAUDE_CODE_', 'CLAUDECODE', 'CODEX_SANDBOX'))}
    env['PATH'] = f"{Path('~/.local/bin').expanduser()}:{env.get('PATH', '/usr/bin:/bin')}"
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


Runner = Callable[..., subprocess.CompletedProcess]


class Workers:
    def __init__(self, cfg: Config, runner: Runner = subprocess.run):
        # Claude worker guard: 'auto' = Claude's auto-mode safety classifier reviews every action
        # (default; the OS sandbox cannot nest under Ubuntu's AppArmor userns restriction here),
        # 'sandbox' = auto mode + OS sandbox (needs nested user namespaces), 'acceptEdits' = legacy.
        # Codex workers already run in Codex's workspace-write sandbox.
        self.claude_guard = cfg['workers'].get('claude_guard', 'auto')
        if cfg['workers'].get('claude_sandbox'):
            self.claude_guard = 'sandbox'
        if self.claude_guard not in ('auto', 'sandbox', 'acceptEdits'):
            raise ValueError(f'unknown workers.claude_guard {self.claude_guard!r}')
        self.codex = str(cfg.path('workers', 'codex'))
        self.claude = str(cfg.path('workers', 'claude'))
        self.timeout = int(cfg['workers']['timeout_s'])
        self.logs = cfg.logs
        self.run = runner
        self._auth_ok: dict[str, float] = {}

    # -- billing preflight ---------------------------------------------------
    def verify_billing(self, cli: str) -> None:
        if time.time() - self._auth_ok.get(cli, 0) < 600:
            return
        if cli == 'codex':
            auth = Path(os.environ.get('CODEX_HOME', '~/.codex')).expanduser() / 'auth.json'
            try:
                data = json.loads(auth.read_text())
            except (OSError, ValueError) as exc:
                raise BillingError(f'cannot read Codex auth: {exc}') from exc
            if data.get('auth_mode') != 'chatgpt' or data.get('OPENAI_API_KEY'):
                raise BillingError('Codex is not on ChatGPT subscription login')
        elif cli == 'claude':
            p = self.run([self.claude, 'auth', 'status'], capture_output=True, text=True,
                         env=child_env(), timeout=60, stdin=subprocess.DEVNULL)
            try:
                st = json.loads(p.stdout)
            except ValueError as exc:
                raise BillingError('cannot read Claude auth status') from exc
            if not (st.get('loggedIn') and st.get('authMethod') == 'claude.ai'
                    and st.get('subscriptionType') in {'max', 'pro', 'team', 'enterprise'}):
                raise BillingError(f'Claude is not on a subscription login: {st.get("authMethod")}')
        else:
            raise BillingError(f'unknown CLI {cli}')
        self._auth_ok[cli] = time.time()

    # -- execution -------------------------------------------------------------
    def execute(self, lane: Lane, prompt: str, cwd: Path, *, write: bool = True,
                extra_dirs: tuple[Path, ...] = (), schema: dict | None = None,
                log_name: str = 'job') -> Result:
        self.verify_billing(lane.cli)
        self.logs.mkdir(parents=True, exist_ok=True)
        log = self.logs / f'{time.strftime("%Y%m%d-%H%M%S")}-{log_name}-{lane.name}.log'
        t0 = time.time()
        if lane.cli == 'codex':
            res = self._codex(lane, prompt, cwd, write, extra_dirs, schema, log)
        else:
            res = self._claude(lane, prompt, cwd, write, extra_dirs, schema, log)
        res.seconds = time.time() - t0
        return res

    def _codex(self, lane, prompt, cwd, write, extra_dirs, schema, log) -> Result:
        out_file = log.with_suffix('.last.txt')
        cmd = [self.codex, 'exec', '-m', lane.model, '-c', f'model_reasoning_effort="{lane.effort}"',
               '-c', 'approval_policy="never"', '--ephemeral', '--json', '--skip-git-repo-check',
               '-s', 'workspace-write' if write else 'read-only', '-C', str(cwd),
               '-o', str(out_file)]
        for d in extra_dirs:
            cmd += ['--add-dir', str(d)]
        schema_file = None
        if schema is not None:
            schema_file = log.with_suffix('.schema.json')
            schema_file.write_text(json.dumps(schema))
            cmd += ['--output-schema', str(schema_file)]
        cmd.append('-')
        try:
            p = self.run(cmd, input=prompt, capture_output=True, text=True, env=child_env(),
                         timeout=self.timeout, cwd=str(cwd))
        except subprocess.TimeoutExpired:
            return Result(False, '', error='timeout')
        log.write_text(f'$ {" ".join(cmd[:-1])}\n--- stdout\n{p.stdout}\n--- stderr\n{p.stderr}')
        usage: dict = {}
        for line in p.stdout.splitlines():
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            if ev.get('type') == 'turn.completed':
                for k, v in (ev.get('usage') or {}).items():
                    usage[k] = usage.get(k, 0) + (v or 0)
        text = out_file.read_text() if out_file.exists() else ''
        if p.returncode != 0 and AUTH_FAILURE.search(p.stdout[-20000:] + p.stderr[-5000:]):
            # A rejected login is an owner problem, not a code problem: never retry/escalate on it.
            self._auth_ok.pop('codex', None)
            raise BillingError('Codex login rejected by the server (401). Re-login with `codex login` '
                               '(ChatGPT account), then `aa answer "retry <task>"`.')
        structured = _json_or_none(text) if schema is not None else None
        ok = p.returncode == 0 and bool(text.strip()) and (schema is None or structured is not None)
        return Result(ok, text, structured, [lane.model] if ok else [], usage,
                      error='' if ok else (p.stderr[-2000:] or f'exit {p.returncode}'))

    def _claude(self, lane, prompt, cwd, write, extra_dirs, schema, log) -> Result:
        # --strict-mcp-config without --mcp-config: no MCP servers or claude.ai connectors in workers.
        cmd = [self.claude, '-p', '--model', lane.model, '--effort', lane.effort,
               '--output-format', 'json', '--no-session-persistence', '--strict-mcp-config']
        if write and self.claude_guard == 'sandbox':
            cmd += ['--permission-mode', 'auto', '--settings', json.dumps(sandbox_settings(cwd, extra_dirs)),
                    '--allowedTools', 'Bash', 'Read', 'Edit', 'Write', 'Glob', 'Grep', 'TodoWrite']
        elif write and self.claude_guard == 'auto':
            cmd += ['--permission-mode', 'auto', '--settings', json.dumps({'permissions': {'deny': WORKER_DENY}}),
                    '--allowedTools', 'Read', 'Edit', 'Write', 'Glob', 'Grep', 'TodoWrite']
        elif write:
            cmd += ['--permission-mode', 'acceptEdits',
                    '--allowedTools', 'Bash', 'Read', 'Edit', 'Write', 'Glob', 'Grep', 'TodoWrite']
        else:
            cmd += ['--permission-mode', 'default', '--allowedTools', 'Read', 'Glob', 'Grep',
                    '--disallowedTools', 'Edit', 'Write', 'Bash']
        for d in extra_dirs:
            cmd += ['--add-dir', str(d)]
        if schema is not None:
            cmd += ['--json-schema', json.dumps(schema)]
        try:
            p = self.run(cmd, input=prompt, capture_output=True, text=True, env=child_env(),
                         timeout=self.timeout, cwd=str(cwd))
        except subprocess.TimeoutExpired:
            return Result(False, '', error='timeout')
        log.write_text(f'$ {" ".join(cmd)}\n--- stdout\n{p.stdout}\n--- stderr\n{p.stderr}')
        data = _json_or_none(p.stdout.strip().splitlines()[-1] if p.stdout.strip() else '')
        if not data:
            err = (p.stderr + p.stdout)[-2000:] or 'no JSON result'
            if 'sandbox required but unavailable' in err:
                raise BillingError('Claude sandbox unavailable (install bubblewrap and socat): ' + err[:300])
            return Result(False, '', error=err)
        if data.get('is_error') and AUTH_FAILURE.search(json.dumps(data)[:20000]):
            self._auth_ok.pop('claude', None)
            raise BillingError('Claude login rejected by the server. Re-login with `claude auth login`, '
                               'then `aa answer "retry <task>"`.')
        seen = list((data.get('modelUsage') or {}).keys())
        text = data.get('result') or ''
        structured = data.get('structured_output')
        if schema is not None and structured is None:
            structured = _json_or_none(text)
        err = ''
        if data.get('is_error'):
            err = text or data.get('api_error_code') or 'claude error'
        elif not any(m.startswith(lane.model) for m in seen):
            err = f'model substitution: requested {lane.model}, observed {seen}'
        elif schema is not None and structured is None:
            err = 'missing structured output'
        usage = {'api_equivalent_usd': data.get('total_cost_usd'), **(data.get('usage') or {})}
        return Result(not err, text, structured, seen, usage, error=err)


# Hard denies for Claude workers, independent of the auto-mode classifier (which honours
# explicitly requested actions): workers never publish, change remotes or escalate privileges.
WORKER_DENY = ['Bash(git push:*)', 'Bash(git remote:*)', 'Bash(git config:*)', 'Bash(sudo:*)',
               'Bash(ssh:*)', 'Bash(scp:*)', 'Bash(gh:*)', 'Read(~/.ssh/**)', 'Read(~/.codex/auth.json)',
               'Read(~/.claude/.credentials.json)', 'Read(~/.config/agenticarch/**)']


def sandbox_settings(cwd: Path, extra_dirs: tuple[Path, ...] = ()) -> dict:
    """Claude Code sandbox: writes only in the job directories, credentials unreadable,
    refuse to start without a working sandbox (never silently unsandboxed)."""
    return {'permissions': {'deny': WORKER_DENY}, 'sandbox': {
        'enabled': True, 'allowUnsandboxedCommands': False, 'failIfUnavailable': True,
        'filesystem': {'allowWrite': [str(cwd), *map(str, extra_dirs)],
                       'denyRead': ['~/.ssh', '~/.codex/auth.json', '~/.claude/.credentials.json',
                                    '~/.config/agenticarch', '~/.local/share/agenticarch/aa.sqlite']},
    }}


def _json_or_none(text: str) -> dict | None:
    text = (text or '').strip()
    if text.startswith('```'):
        text = text.strip('`')
        text = text[text.find('{'):]
    try:
        v = json.loads(text)
    except ValueError:
        start, end = text.find('{'), text.rfind('}')
        if start < 0 or end <= start:
            return None
        try:
            v = json.loads(text[start:end + 1])
        except ValueError:
            return None
    return v if isinstance(v, dict) else None
