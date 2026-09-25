"""CLM choice adapter: prose encoders, strict replies and loopback-only HTTP.

Implements the upstream /v1/systemone choice contract. No model installation,
permission grant, calibration claim or coding-worker execution is performed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
import json
import math
import re
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

IDENTIFIER = re.compile(r'^[a-z][a-z0-9_.-]{0,79}$')
PROVENANCE = ('encoder_revision', 'tokenizer_revision', 'head_sha256',
              'pooling', 'runtime_revision', 'renderer_version')


def _json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def render_state(fields: Mapping[str, Any]) -> str:
    """Render bounded projected evidence, not the whole policy registry."""
    if not fields or any(not isinstance(k, str) or not k.strip() for k in fields):
        raise ValueError('Named evidence fields required')
    def text(value: Any) -> str:
        if isinstance(value, str):
            return value
        if value is None:
            return 'unknown'
        if type(value) in (bool, int, float):
            return _json(value).decode()
        if isinstance(value, list):
            return '\n'.join('- ' + text(v) for v in value)
        if isinstance(value, dict):
            return render_state(value)
        raise ValueError('Unsupported evidence value')
    return '\n\n'.join(f'{k}: {text(v)}' for k, v in fields.items())


@dataclass(frozen=True)
class PreparedChoice:
    body: bytes
    binding: bytes
    request_id: str

    def intact(self) -> bool:
        return hashlib.sha256(self.binding + b'\n' + self.body).hexdigest() == self.request_id


def prepare_choice(state: str, question: str, criteria: Mapping[str, str], *,
                   model: str, provenance: Mapping[str, str],
                   token_counter: Callable[[str], int], max_tokens: int,
                   question_id: str = 'decision', max_bytes: int = 131072) -> PreparedChoice:
    """Use the exact deployed tokenizer. Fail before upstream can truncate."""
    if not all(isinstance(x, str) and x.strip() for x in (state, question, model)):
        raise ValueError('State, question and explicit served model are required')
    if not IDENTIFIER.fullmatch(question_id):
        raise ValueError('Invalid question ID')
    if type(max_tokens) is not int or max_tokens < 1:
        raise ValueError('Invalid encoder token limit')
    if not 2 <= len(criteria) <= 16 or 'insufficient' not in criteria:
        raise ValueError('Require 2..16 choices including insufficient')
    if any(not isinstance(k, str) or not IDENTIFIER.fullmatch(k) or
           not isinstance(v, str) or not v.strip() for k, v in criteria.items()):
        raise ValueError('Choices need stable IDs and nonempty prose descriptions')
    if len({v.strip() for v in criteria.values()}) != len(criteria):
        raise ValueError('Duplicate candidate descriptions are ambiguous')
    if any(not isinstance(provenance.get(k), str) or not provenance[k].strip() for k in PROVENANCE):
        raise ValueError('Incomplete CLM deployment provenance')
    if not re.fullmatch('[0-9a-f]{64}', provenance['head_sha256']):
        raise ValueError('Pin the head bytes, not a moving model alias')
    for value in (state.strip() + '\n\n' + question.strip(), *criteria.values()):
        count = token_counter(value)
        if type(count) is not int or count < 1 or count > max_tokens:
            raise ValueError('Encoder budget exceeded or token count invalid; do not truncate')
    body = _json({'model': model, 'state': state.strip(), 'questions': {
        question_id: {'type': 'choice', 'instructions': question.strip(), 'criteria': dict(criteria)}
    }})
    if type(max_bytes) is not int or max_bytes < 1 or len(body) > max_bytes:
        raise ValueError('Request byte budget exceeded')
    binding = _json({'provenance': dict(provenance), 'max_tokens': max_tokens,
                     'ordered_options': list(criteria)})
    return PreparedChoice(body, binding, hashlib.sha256(binding + b'\n' + body).hexdigest())


def normalize_choice(prepared: PreparedChoice, response: Mapping[str, Any]) -> dict[str, Any]:
    if not prepared.intact():
        raise ValueError('Request was modified')
    request = json.loads(prepared.body)
    qid, question = next(iter(request['questions'].items()))
    answers = response.get('answers')
    if response.get('model') != request['model'] or not isinstance(answers, dict) or set(answers) != {qid}:
        raise ValueError('Wrong model or question set')
    answer = answers[qid]
    if not isinstance(answer, dict) or answer.get('type') != 'choice':
        raise ValueError('Expected a typed choice answer')
    scores = answer.get('probabilities')
    if not isinstance(scores, dict) or set(scores) != set(question['criteria']):
        raise ValueError('Wrong option set')
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in scores.values()):
        raise ValueError('Invalid probabilities')
    if not math.isclose(sum(scores.values()), 1, abs_tol=1e-6):
        raise ValueError('Unnormalized probabilities')
    best = max(scores.values())
    winners = [k for k, v in scores.items() if abs(v - best) <= 1e-12]
    if answer.get('choice') not in winners:
        raise ValueError('Choice is not an argmax')
    selected = winners[0] if len(winners) == 1 else None
    return {'request_id': prepared.request_id, 'scores': scores, 'selected': selected,
            'status': 'ABSTAIN' if selected in (None, 'insufficient') else 'SUGGEST',
            'calibration': 'uncalibrated',
            'separation': best - (sum(scores.values()) - best) / (len(scores) - 1),
            'deployment_binding': json.loads(prepared.binding)}


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('CLM redirects are not allowed')


class LocalCLM:
    """A bounded local HTTP transport. The caller owns service identity/freshness."""
    def __init__(self, base_url: str, *, timeout: float = 10.0,
                 api_key: str | None = None, max_response_bytes: int = 262144):
        url = urlsplit(base_url)
        try:
            address = ipaddress.ip_address(url.hostname or '')
            port = url.port
        except ValueError as exc:
            raise ValueError('Use a literal loopback address') from exc
        if (url.scheme not in {'http', 'https'} or not address.is_loopback or
                url.username is not None or url.password is not None or
                url.path not in ('', '/') or url.query or url.fragment or port is None):
            raise ValueError('Only an explicit loopback origin and port are allowed')
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError('Invalid bounded timeout')
        if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= 1048576:
            raise ValueError('Invalid response budget')
        if api_key is not None and (not isinstance(api_key, str) or not api_key or '\r' in api_key or '\n' in api_key):
            raise ValueError('Invalid local API key')
        self.url = base_url.rstrip('/') + '/v1/systemone'
        self.timeout, self.max_response_bytes = timeout, max_response_bytes
        self._api_key = api_key
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def choose(self, prepared: PreparedChoice) -> dict[str, Any]:
        if not prepared.intact():
            raise ValueError('Request was modified')
        headers = {'Content-Type': 'application/json'}
        if self._api_key:
            headers['Authorization'] = 'Bearer ' + self._api_key
        try:
            with self._opener.open(Request(self.url, data=prepared.body, headers=headers,
                                           method='POST'), timeout=self.timeout) as reply:
                if reply.status != 200:
                    raise ValueError('Unexpected CLM HTTP status')
                raw = reply.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                raise ValueError('CLM response too large')
            return normalize_choice(prepared, json.loads(raw))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            # Do not expose endpoint bodies, credentials or private state in errors.
            raise RuntimeError('Local CLM unavailable; use the controller fallback') from None
