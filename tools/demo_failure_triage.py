#!/usr/bin/env python3
"""Demo of aa/failure_triage.py on a throwaway repo with four real failing checks.

  python3 tools/demo_failure_triage.py      (needs the aa-semif service)
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aa import checks, config  # noqa: E402
from aa.db import DB  # noqa: E402
from aa.failure_triage import triage  # noqa: E402
from aa.semif import SemIf  # noqa: E402

BASE = {
    'calc.py': 'def add(a, b):\n    return a + b\n',
    'legacy_test.py': 'import sys\nprint("AssertionError: legacy export expects 3 columns, got 2")\nsys.exit(1)\n',
}
WORKER_CHANGE = {  # what the "worker" committed on top of the base
    'calc.py': 'def add(a, b):\n    return a - b   # worker bug\n',
    'test_calc.py': 'from calc import add\nassert add(2, 3) == 5, f"add(2, 3) returned {add(2, 3)}, expected 5"\n',
    'test_db.py': ('import socket\ns = socket.socket()\ns.settimeout(1)\ntry:\n    s.connect(("127.0.0.1", 5999))\n'
                   'except OSError as e:\n    raise SystemExit(f"psycopg.OperationalError: connection to server at '
                   '\\"127.0.0.1\\", port 5999 failed: {e}. Is the server running on that host and accepting '
                   'TCP/IP connections?")\n'),
    'test_flaky.py': ('import pathlib, sys\nm = pathlib.Path("/tmp/aa-demo-flaky-ran")\n'
                      'if not m.exists():\n    m.write_text("1")\n    print("TimeoutError: request to '
                      'http://127.0.0.1:8123/ready timed out after 2.0s")\n    sys.exit(1)\n'),
}
CHECKS = {
    'unit': 'python3 test_calc.py',
    'db_integration': 'python3 test_db.py',
    'api_smoke': 'python3 test_flaky.py',
    'legacy_export': 'python3 legacy_test.py',
}


def sh(cwd, *a):
    return subprocess.run(a, cwd=cwd, check=True, capture_output=True, text=True).stdout


def main() -> int:
    Path('/tmp/aa-demo-flaky-ran').unlink(missing_ok=True)
    decider = SemIf(config.load(), DB(':memory:'))
    if not decider.available():
        raise SystemExit('start the SemIf service: systemctl --user start aa-semif')
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / 'repo'
        repo.mkdir()
        sh(repo, 'git', 'init', '-q', '-b', 'main')
        for k, v in BASE.items():
            (repo / k).write_text(v)
        sh(repo, 'git', 'add', '-A')
        sh(repo, 'git', '-c', 'user.name=d', '-c', 'user.email=d@d', 'commit', '-qm', 'base')
        base = sh(repo, 'git', 'rev-parse', 'HEAD').strip()
        for k, v in WORKER_CHANGE.items():
            (repo / k).write_text(v)
        sh(repo, 'git', 'add', '-A')
        sh(repo, 'git', '-c', 'user.name=d', '-c', 'user.email=d@d', 'commit', '-qm', 'worker')
        base_wt = Path(tmp) / 'base'
        sh(repo, 'git', 'worktree', 'add', '-q', '--detach', str(base_wt), base)

        def run_on_base(cmd):
            return checks.run({'base': cmd}, base_wt)[0]

        results = checks.run(CHECKS, repo)
        print(f'{"check":16} {"first run":10} {"decision":13} reason')
        for r in results:
            if r.ok:
                print(f'{r.name:16} {"pass":10} {"-":13}')
                continue
            v = triage(r, repo, run_on_base, decider)
            extra = f' (p_env={v.probs["environment"]:.2f})' if v.probs else ''
            print(f'{r.name:16} {"FAIL":10} {v.action:13} {v.reason}{extra}')
        print('\nWhat aa would do: CODE -> back to the worker with the output; ENVIRONMENT -> pause the task\n'
              'and ping you (no retry, no escalation); FLAKY -> continue, logged; PRE_EXISTING -> continue,\n'
              'reported in the delivery note instead of blamed on the worker.')
    Path('/tmp/aa-demo-flaky-ran').unlink(missing_ok=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
