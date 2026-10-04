"""Local SemIf decider (Qwen3.5-4B typed option logits) over a Unix socket.

Same interface as aa.clm.CLM (available/choose/rank) so the daemon can use either;
SemIf is the default after the 2026-09-25 benchmark (eval/results/). The server runs
in a --network none container (deploy/semif/semif_server.py). Failures return None
and callers fall back deterministically; there is never a cloud fallback.
"""
from __future__ import annotations

import http.client
import json
import math
import socket
from pathlib import Path
from typing import Mapping

from .config import Config
from .db import DB


class _UnixHTTP(http.client.HTTPConnection):
    def __init__(self, path: str, timeout: float):
        super().__init__('localhost', timeout=timeout)
        self._path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self._path)


class SemIf:
    backend = 'semif'

    def __init__(self, cfg: Config, db: DB):
        c = cfg['semif']
        self.db, self.enabled = db, bool(c.get('enabled', True))
        self.sock = str(Path(c['socket']).expanduser())
        self.timeout = float(c.get('timeout_s', 30))

    def _call(self, method: str, path: str, body: dict | None = None) -> dict:
        conn = _UnixHTTP(self.sock, self.timeout)
        try:
            data = json.dumps(body).encode() if body is not None else None
            conn.request(method, path, data, {'Content-Type': 'application/json'} if data else {})
            resp = conn.getresponse()
            payload = json.loads(resp.read(2_000_000))
            if resp.status != 200:
                raise ValueError(f'SemIf HTTP {resp.status}: {payload}')
            return payload
        finally:
            conn.close()

    def available(self) -> bool:
        if not self.enabled or not Path(self.sock).exists():
            return False
        try:
            return bool(self._call('GET', '/health').get('ok'))
        except (OSError, ValueError):
            return False

    def _probs(self, state: str, question: str, options: Mapping[str, str]) -> dict[str, float]:
        res = self._call('POST', '/v1/decide', {
            'state': state, 'question': question,
            'options': [{'id': k, 'description': v} for k, v in options.items()]})
        probs = dict(zip(res['option_ids'], res['probabilities']))
        if (set(probs) != set(options) or
                not all(isinstance(p, (int, float)) and math.isfinite(p) and 0 <= p <= 1 for p in probs.values())
                or not math.isclose(sum(probs.values()), 1.0, abs_tol=1e-4)):
            raise ValueError('SemIf response does not match the declared options')
        return probs

    def choose(self, kind: str, task_id: str | None, state: str, question: str,
               options: Mapping[str, str]) -> tuple[str | None, dict | None, int]:
        probs: dict | None = None
        proposed: str | None = None
        if self.available():
            try:
                probs = self._probs(state, question, options)
                proposed = max(probs, key=probs.get)
            except Exception as exc:
                self.db.event('decider_error', task_id, backend='semif', decision=kind, error=repr(exc)[:300])
                probs = None
        did = self.db.decision(kind, task_id, state, dict(options), probs, proposed, None)
        return proposed, probs, did

    def rank(self, task_id: str | None, context: str, question: str,
             candidates: list[str], k: int) -> list[str]:
        """Relevance per candidate as a yes/no choice; fallback keeps the input order."""
        ranked = candidates[:k]
        if candidates and self.available():
            try:
                scores = {}
                for c in candidates:
                    p = self._probs(f'Task: {context}\n\nCandidate: {c}', question,
                                    {'relevant': 'Relevant to the task.',
                                     'irrelevant': 'Not relevant to the task.'})
                    scores[c] = p['relevant']
                ranked = sorted(candidates, key=lambda c: -scores[c])[:k]
            except Exception as exc:
                self.db.event('decider_error', task_id, backend='semif', decision='context', error=repr(exc)[:300])
        self.db.decision('context', task_id, context[:4000], {'candidates': candidates}, None,
                         None, json.dumps(ranked))
        return ranked
