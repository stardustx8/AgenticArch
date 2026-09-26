"""Bounded Claude Stop-check hook, copied to a coordinator-owned capsule.

This is a latency experiment, NOT a security or completion boundary. It uses
only frozen check commands, never the repository's current configuration. All
checks still run in the coordinator after the worker session ends.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from string import Template


class CheckTimeout(Exception):
    pass


def run_command(command: str, cwd: Path, timeout: float) -> tuple[int, str]:
    """Bound wall time and output memory; terminate ordinary process descendants."""
    with tempfile.TemporaryFile() as output:
        p = subprocess.Popen(command, shell=True, cwd=cwd, stdin=subprocess.DEVNULL,
                             stdout=output, stderr=subprocess.STDOUT, start_new_session=True,
                             env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        def terminate(*_):
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.wait()
            raise CheckTimeout('check interrupted or timed out')
        old = signal.signal(signal.SIGTERM, terminate)
        try:
            try:
                code = p.wait(timeout=max(.01, timeout))
            except subprocess.TimeoutExpired:
                terminate()
            output.seek(0, os.SEEK_END)
            output.seek(max(0, output.tell() - 3000))
            return code, output.read().decode('utf-8', errors='replace')
        finally:
            signal.signal(signal.SIGTERM, old)
            if p.poll() is None:
                try:
                    os.killpg(p.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                p.wait()


def evaluate(policy: dict, payload: dict, blocks: int) -> tuple[dict, int, dict]:
    """Return the hook reply, new count and audit entry; no DB or git writes."""
    audit = {'event': 'ignored', 'blocks': blocks, 'ts': time.time()}
    if (payload.get('hook_event_name') != 'Stop' or
            Path(str(payload.get('cwd', ''))).resolve() != Path(policy['cwd']).resolve()):
        return {}, blocks, audit
    if blocks >= policy['max_blocks']:
        audit['event'] = 'cap_reached'
        return {}, blocks, audit
    if not policy['checks']:
        audit['event'] = 'no_checks'
        return {}, blocks, audit
    failures = []
    started = time.monotonic()
    deadline = started + policy['timeout_s']
    for name, command in policy['checks'].items():
        try:
            left = deadline - time.monotonic()
            if left <= 0:
                raise CheckTimeout('batch timeout')
            code, text = run_command(command, Path(policy['cwd']), left)
        except CheckTimeout as exc:
            # A hanging/environmental check should not consume the whole repair
            # budget again. End the hook loop; coordinator verification is intact.
            audit.update(event='timeout', seconds=time.monotonic() - started)
            return {}, policy['max_blocks'], audit
        if code:
            failures.append(f'[{name}; exit={code}]\n{text}')
    audit.update(seconds=time.monotonic() - started, failed=len(failures))
    if not failures:
        audit['event'] = 'checks_passed'
        return {}, blocks, audit
    blocks += 1
    audit.update(event='checks_failed', blocks=blocks)
    reason = Template(policy['reason_template']).safe_substitute(failures='\n\n'.join(failures)[:6000])
    return {'decision': 'block', 'reason': reason}, blocks, audit


def install(settings: dict, checks: dict, cwd: Path, root: Path, *, max_blocks: int,
            timeout_s: float, reason_template: str) -> dict:
    """Create an isolated per-dispatch capsule and merge, never replace, settings."""
    if not 1 <= max_blocks <= 5 or not 0 < timeout_s <= 300:
        raise ValueError('Stop checks need 1..5 blocks and a timeout in (0, 300] seconds')
    if not all(isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in checks.items()):
        raise ValueError('invalid frozen checks')
    if root.resolve().is_relative_to(cwd.resolve()):
        raise ValueError('Stop capsule must be outside the worker worktree')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    capsule = Path(tempfile.mkdtemp(prefix='dispatch-', dir=root))
    policy = {'schema_version': 1, 'cwd': str(cwd.resolve()), 'checks': dict(checks),
              'max_blocks': max_blocks, 'timeout_s': timeout_s, 'reason_template': reason_template}
    data = json.dumps(policy, sort_keys=True).encode()
    (capsule / 'policy.json').write_bytes(data)
    (capsule / 'hook.py').write_bytes(Path(__file__).read_bytes())
    import shlex
    command = shlex.join([sys.executable, '-I', str(capsule / 'hook.py'),
                          '--policy', str(capsule / 'policy.json'),
                          '--sha256', hashlib.sha256(data).hexdigest()])
    result = json.loads(json.dumps(settings))
    result.setdefault('hooks', {}).setdefault('Stop', []).append(
        {'hooks': [{'type': 'command', 'command': command, 'timeout': timeout_s + 5}]})
    denies = result.setdefault('permissions', {}).setdefault('deny', [])
    denies.extend([f'Write({capsule}/**)', f'Edit({capsule}/**)'])
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--policy', required=True, type=Path)
    ap.add_argument('--sha256', required=True)
    a = ap.parse_args()
    audit = {'event': 'invalid_input', 'ts': time.time()}
    reply = {}
    try:
        raw = a.policy.read_bytes()
        if hashlib.sha256(raw).hexdigest() != a.sha256:
            raise ValueError('frozen policy checksum mismatch')
        policy = json.loads(raw)
        # Bound stdin. Oversized or invalid input never requests another turn.
        payload_text = sys.stdin.read(65537)
        if len(payload_text) > 65536:
            raise ValueError('hook input is too large')
        payload = json.loads(payload_text)
        if not isinstance(payload, dict):
            raise ValueError('hook input must be an object')
        with (a.policy.parent / 'counter').open('a+') as counter:
            fcntl.flock(counter, fcntl.LOCK_EX)
            counter.seek(0)
            previous = counter.read().strip()
            blocks = int(previous) if previous else 0
            if blocks < 0:
                raise ValueError('invalid hook counter')
            reply, blocks, audit = evaluate(policy, payload, blocks)
            counter.seek(0)
            counter.truncate()
            counter.write(str(blocks))
            counter.flush()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        audit['error'] = type(exc).__name__
    try:
        with (a.policy.parent / 'events.jsonl').open('a') as f:
            f.write(json.dumps(audit) + '\n')
    except OSError:
        pass
    print(json.dumps(reply))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
