"""Pinned CLM wire adapter. Network access is explicitly loopback-only.

This client supplies validation, not attestation: deployment_digest() and count_tokens()
must come from a trusted supervisor and the pinned encoder tokenizer respectively.
No model download, training, command execution, cloud fallback or automatic dispatch.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


def canonical_digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def loopback_url(value: str) -> str:
    p = urlsplit(value)
    if (p.scheme != 'http' or p.hostname not in {'127.0.0.1', '::1'} or
            p.username is not None or p.password is not None or
            p.query or p.fragment or p.path not in {'', '/'} or
            p.port is None or not 1 <= p.port <= 65535):
        raise ValueError('Require an explicit HTTP loopback IP and port, without credentials or path')
    return value.rstrip('/')


def prepare_request(state: str, question: str, criteria: Mapping[str, str], *,
                    model: str, count_tokens: Callable[[str], int], max_tokens: int) -> dict:
    if type(max_tokens) is not int or max_tokens < 1:
        raise ValueError('Invalid encoder limit')
    if not all(isinstance(x, str) and x.strip() for x in (state, question, model)):
        raise ValueError('State, question and model are required')
    if not 2 <= len(criteria) <= 32:
        raise ValueError('Project limit: two to 32 distinct options')
    if not all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
               for k, v in criteria.items()):
        raise ValueError('Each option needs a stable ID and a meaningful description')
    if len(set(criteria.values())) != len(criteria):
        raise ValueError('Duplicate action descriptions cannot distinguish options')
    # CLM schema.py puts the question LAST. Check this exact text, not just state.
    for text in (state.strip() + '\n\n' + question.strip(), *criteria.values()):
        n = count_tokens(text)
        if type(n) is not int or n < 1 or n > max_tokens:
            raise ValueError('Tokenizer missing/invalid or CLM input would be truncated')
    return {'model': model, 'state': state, 'questions': {'route': {
        'type': 'choice', 'instructions': question, 'criteria': dict(criteria)}}, 'temperature': 1.0}


@dataclass(frozen=True)
class Choice:
    selected: str
    probabilities: dict[str, float]
    confidence: float  # Upstream separation statistic, NOT probability of correctness.
    request_digest: str
    deployment_digest: str


def parse_choice(body: dict, request: dict, deployment_digest: str) -> Choice:
    if not isinstance(body, dict) or body.get('model') != request['model']:
        raise ValueError('Wrong response model')
    answers = body.get('answers')
    if not isinstance(answers, dict) or set(answers) != {'route'}:
        raise ValueError('Unexpected question set')
    answer = answers['route']
    if not isinstance(answer, dict) or answer.get('type') != 'choice':
        raise ValueError('Expected typed choice')
    probs = answer.get('probabilities')
    options = request['questions']['route']['criteria']
    if not isinstance(probs, dict) or set(probs) != set(options):
        raise ValueError('Wrong option set')
    for p in probs.values():
        if type(p) not in (int, float) or not math.isfinite(p) or not 0 <= p <= 1:
            raise ValueError('Invalid probability')
    if not math.isclose(sum(probs.values()), 1.0, abs_tol=1e-6):
        raise ValueError('Probability mass does not sum to one')
    selected = answer.get('choice')
    if selected not in probs or abs(probs[selected] - max(probs.values())) > 1e-12:
        raise ValueError('Choice is not an argmax')
    reported = answer.get('confidence')
    expected = max(probs.values()) - (sum(probs.values()) - max(probs.values())) / (len(probs) - 1)
    if (type(reported) not in (int, float) or not math.isfinite(reported) or
            not math.isclose(reported, expected, abs_tol=1e-6)):
        raise ValueError('Unexpected CLM confidence semantics')
    return Choice(selected, dict(probs), float(reported), canonical_digest(request), deployment_digest)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class CLMClient:
    def __init__(self, base_url: str, model: str, *, deployment: str,
                 deployment_digest: Callable[[], str], count_tokens: Callable[[str], int],
                 max_tokens: int = 2048, timeout: float = 10.0, api_key: str | None = None):
        self.base_url = loopback_url(base_url)
        if len(deployment) != 64 or any(c not in '0123456789abcdef' for c in deployment):
            raise ValueError('A pinned deployment SHA-256 is required')
        if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= 60:
            raise ValueError('Invalid bounded timeout')
        self.model, self.deployment = model, deployment
        self._attest, self._count = deployment_digest, count_tokens
        self.max_tokens, self.timeout, self._key = max_tokens, timeout, api_key
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def score(self, state: str, question: str, criteria: Mapping[str, str]) -> Choice:
        payload = prepare_request(state, question, criteria, model=self.model,
                                  count_tokens=self._count, max_tokens=self.max_tokens)
        if self._attest() != self.deployment:
            raise ValueError('CLM deployment changed or is unqualified')
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
        if self._key:
            headers['Authorization'] = 'Bearer ' + self._key
        req = Request(self.base_url + '/v1/systemone',
                      data=json.dumps(payload, allow_nan=False).encode(), headers=headers, method='POST')
        with self._opener.open(req, timeout=self.timeout) as response:
            if response.status != 200 or response.headers.get_content_type() != 'application/json':
                raise ValueError('Unexpected CLM HTTP response')
            raw = response.read(1_048_577)
        if len(raw) > 1_048_576:
            raise ValueError('Oversized CLM response')
        if self._attest() != self.deployment:
            raise ValueError('CLM changed during scoring; invalidate this result')
        return parse_choice(json.loads(raw), payload, self.deployment)
