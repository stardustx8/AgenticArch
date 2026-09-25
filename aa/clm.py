"""Local CLM decisions with strict validation and decision logging.

Wraps reference/clm.py (loopback-only client, exact-token preflight, response
validation). Every call is logged to the `decisions` table so outcomes can later
be used to evaluate or fine-tune CLM. Unavailable CLM returns None; callers fall
back to deterministic behaviour and never to a cloud classifier.
"""
from __future__ import annotations

import hashlib
import json
import math
import urllib.request
from pathlib import Path
from typing import Mapping

from reference.clm import CLMClient, canonical_digest, loopback_url

from .config import Config
from .db import DB


class CLM:
    def __init__(self, cfg: Config, db: DB):
        c = cfg['clm']
        self.cfg, self.db, self.enabled = c, db, bool(c.get('enabled', True))
        self.url = c['url'].rstrip('/')
        self.max_tokens = int(c['max_tokens'])
        self._ckpt = Path(c['checkpoint']).expanduser()
        self._ckpt_digest: tuple[float, str] | None = None
        self._client: CLMClient | None = None

    # -- trusted local observations -------------------------------------
    def count_tokens(self, text: str) -> int:
        body = json.dumps({'model': self.cfg['encoder_model'], 'prompt': text}).encode()
        req = urllib.request.Request(loopback_url(self.cfg['tokenize_url'].rsplit('/', 1)[0]) + '/tokenize',
                                     data=body, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=10) as r:
            return int(json.load(r)['count'])

    def deployment_digest(self) -> str:
        st = self._ckpt.stat()
        if not self._ckpt_digest or self._ckpt_digest[0] != st.st_mtime:
            h = hashlib.sha256()
            with open(self._ckpt, 'rb') as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b''):
                    h.update(chunk)
            self._ckpt_digest = (st.st_mtime, h.hexdigest())
        with urllib.request.urlopen(self.url + '/v1/models', timeout=5) as r:
            models = json.load(r)
        return canonical_digest({'ckpt': self._ckpt_digest[1], 'models': models,
                                 'encoder': self.cfg['encoder_model'], 'max_tokens': self.max_tokens})

    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            with urllib.request.urlopen(self.url + '/health', timeout=3) as r:
                return bool(json.load(r).get('ok'))
        except (OSError, ValueError):
            return False

    def _get_client(self) -> CLMClient:
        if self._client is None:
            self._client = CLMClient(self.url, self.cfg['model'], deployment=self.deployment_digest(),
                                     deployment_digest=self.deployment_digest,
                                     count_tokens=self.count_tokens, max_tokens=self.max_tokens,
                                     timeout=float(self.cfg['timeout_s']))
        return self._client

    def _fit(self, state: str, question: str) -> tuple[str, bool]:
        """Trim the state explicitly (and record it) instead of silent server truncation."""
        trimmed = False
        budget = self.max_tokens - 16
        while self.count_tokens(state.strip() + '\n\n' + question.strip()) > budget:
            state = state[: int(len(state) * 0.8)]
            trimmed = True
            if len(state) < 200:
                raise ValueError('question alone exceeds the CLM token budget')
        return (state + '\n[trimmed]' if trimmed else state), trimmed

    # -- decisions -----------------------------------------------------------
    def choose(self, kind: str, task_id: str | None, state: str, question: str,
               options: Mapping[str, str]) -> tuple[str | None, dict | None, int]:
        """Return (argmax option or None, probabilities or None, decision row id)."""
        probs: dict | None = None
        proposed: str | None = None
        if self.available():
            try:
                state, _ = self._fit(state, question)
                choice = self._get_client().score(state, question, dict(options))
                probs, proposed = choice.probabilities, choice.selected
            except Exception as exc:  # Any CLM failure => deterministic fallback.
                self.db.event('clm_error', task_id, kind=kind, error=repr(exc)[:300])
                self._client = None
        did = self.db.decision(kind, task_id, state, dict(options), probs, proposed, None)
        return proposed, probs, did

    def rank(self, task_id: str | None, context: str, question: str,
             candidates: list[str], k: int) -> list[str]:
        """Rank candidate texts (e.g. file paths + first lines); fallback keeps input order."""
        ranked: list[str] = candidates[:k]
        if candidates and self.available():
            try:
                context, _ = self._fit(context, question)
                body = json.dumps({'context': context, 'question': question,
                                   'answers': candidates, 'model': self.cfg['model']}).encode()
                req = urllib.request.Request(self.url + '/v1/rank', data=body,
                                             headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req, timeout=float(self.cfg['timeout_s'])) as r:
                    out = json.load(r)['ranked']
                cands = [x['candidate'] for x in out]
                probs = [x['prob'] for x in out]
                if (sorted(cands) != sorted(candidates) or
                        not all(isinstance(p, (int, float)) and math.isfinite(p) for p in probs)):
                    raise ValueError('rank response does not match candidates')
                ranked = cands[:k]
            except Exception as exc:
                self.db.event('clm_error', task_id, kind='context', error=repr(exc)[:300])
        self.db.decision('context', task_id, context[:4000], {'candidates': candidates}, None,
                         None, json.dumps(ranked))
        return ranked
