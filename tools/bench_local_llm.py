#!/usr/bin/env python3
"""Benchmark the local model server (quality + speed) for aa's two local jobs.

Workloads against an OpenAI-compatible endpoint (default: aa-gemma on :8100):
  judge   - blind spec-conformance probe, test split (accuracy, latency)
  tests   - 12 function specs with hidden reference implementations: a generated test set is
            VALID only if it fails on the base module and passes on the reference (+ syntax ok);
            also records degenerate outputs (finish_reason=length)
  speed   - decode tokens/s on a fixed long generation
Usage: python3 tools/bench_local_llm.py --label fp8-ws-off [--url ...] [--model ...]
Results append to eval/results/local-llm-bench.jsonl.
"""
from __future__ import annotations

import argparse
import ast
import json
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aa.quality import LOCAL_ORACLE_SCHEMA  # noqa: E402

BASE = 'def add(a, b):\n    return a + b\n'
EXAMPLE_TEST = ('import unittest\nfrom mod import add\n\n\nclass T(unittest.TestCase):\n'
                '    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n')
SPECS = [  # (name, spec, reference implementation)
    ('median', 'median(values) returns the median of a non-empty list of numbers (mean of the two middle values for '
     'even length) and raises ValueError for an empty list.',
     'def median(values):\n    if not values:\n        raise ValueError("empty")\n    s = sorted(values)\n'
     '    n = len(s)\n    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2\n'),
    ('is_prime', 'is_prime(n) returns True for prime integers and False otherwise (0, 1 and negatives are not prime).',
     'def is_prime(n):\n    if n < 2:\n        return False\n    i = 2\n    while i * i <= n:\n        if n % i == 0:\n'
     '            return False\n        i += 1\n    return True\n'),
    ('gcd', 'gcd(a, b) returns the greatest common divisor of two integers as a non-negative number; gcd(0, 0) is 0.',
     'def gcd(a, b):\n    a, b = abs(a), abs(b)\n    while b:\n        a, b = b, a % b\n    return a\n'),
    ('fizzbuzz', 'fizzbuzz(n) returns a list of strings for 1..n: "Fizz" for multiples of 3, "Buzz" for multiples of 5, '
     '"FizzBuzz" for both, otherwise the number as a string.',
     'def fizzbuzz(n):\n    out = []\n    for i in range(1, n + 1):\n        s = ("Fizz" if i % 3 == 0 else "") + '
     '("Buzz" if i % 5 == 0 else "")\n        out.append(s or str(i))\n    return out\n'),
    ('word_count', 'word_count(text) returns a dict mapping lowercase words to their counts; words are separated by '
     'whitespace and surrounding punctuation .,!? is stripped.',
     'def word_count(text):\n    d = {}\n    for w in text.split():\n        w = w.strip(".,!?").lower()\n'
     '        if w:\n            d[w] = d.get(w, 0) + 1\n    return d\n'),
    ('rle_encode', 'rle_encode(s) run-length encodes a string, e.g. "aaabcc" -> "a3b1c2"; the empty string encodes to "".',
     'def rle_encode(s):\n    out, i = [], 0\n    while i < len(s):\n        j = i\n        while j < len(s) and s[j] == s[i]:\n'
     '            j += 1\n        out.append(f"{s[i]}{j - i}")\n        i = j\n    return "".join(out)\n'),
    ('roman_to_int', 'roman_to_int(s) converts a valid Roman numeral (I, V, X, L, C, D, M with subtractive notation) '
     'to an integer.',
     'def roman_to_int(s):\n    v = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}\n    total = 0\n'
     '    for i, c in enumerate(s):\n        if i + 1 < len(s) and v[c] < v[s[i + 1]]:\n            total -= v[c]\n'
     '        else:\n            total += v[c]\n    return total\n'),
    ('flatten', 'flatten(items) flattens arbitrarily nested lists into a single list, preserving order; non-list items '
     '(including tuples and strings) are kept as they are.',
     'def flatten(items):\n    out = []\n    for x in items:\n        out.extend(flatten(x) if isinstance(x, list) else [x])\n'
     '    return out\n'),
    ('chunk', 'chunk(items, n) splits a list into consecutive lists of length n (the last may be shorter) and raises '
     'ValueError if n < 1.',
     'def chunk(items, n):\n    if n < 1:\n        raise ValueError("n")\n    return [items[i:i + n] for i in range(0, len(items), n)]\n'),
    ('safe_divide', 'safe_divide(a, b) returns a / b, and raises ZeroDivisionError with the message '
     '"cannot divide by zero" when b is 0.',
     'def safe_divide(a, b):\n    if b == 0:\n        raise ZeroDivisionError("cannot divide by zero")\n    return a / b\n'),
    ('parse_bool', 'parse_bool(s) returns True for "true", "yes", "1", "on" and False for "false", "no", "0", "off" '
     '(case-insensitive, surrounding whitespace ignored) and raises ValueError otherwise.',
     'def parse_bool(s):\n    t = s.strip().lower()\n    if t in ("true", "yes", "1", "on"):\n        return True\n'
     '    if t in ("false", "no", "0", "off"):\n        return False\n    raise ValueError(s)\n'),
    ('clamp', 'clamp(x, lo, hi) returns x limited to the inclusive range [lo, hi] and raises ValueError when lo > hi.',
     'def clamp(x, lo, hi):\n    if lo > hi:\n        raise ValueError("lo > hi")\n    return max(lo, min(x, hi))\n'),
]


OPTS = {'sampling': {'temperature': 0.2}, 'chat_template_kwargs': {}, 'rep_detect': True, 'max_tokens': 4096}


def chat(url, model, prompt, schema=None, max_tokens=4096):
    body = {'model': model, 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': max_tokens,
            **OPTS['sampling']}
    if OPTS['rep_detect']:
        body['repetition_detection'] = {'max_pattern_size': 20, 'min_pattern_size': 1, 'min_count': 6}
    if OPTS['chat_template_kwargs']:
        body['chat_template_kwargs'] = OPTS['chat_template_kwargs']
    if schema:
        body['response_format'] = {'type': 'json_schema', 'json_schema': {'name': 'r', 'schema': schema, 'strict': True}}
    req = urllib.request.Request(url + '/v1/chat/completions', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json'})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=900) as r:
        d = json.load(r)
    dt = time.perf_counter() - t0
    ch = d['choices'][0]
    fin = 'length' if ch.get('stop_reason') == 'repetition_detected' else ch.get('finish_reason')
    return ch['message'].get('content') or '', fin, d.get('usage', {}).get('completion_tokens', 0), dt


def bench_judge(url, model):
    from tools.eval_probe import PROBES
    q, opts = PROBES['spec_conformance']['variants']['matches']
    rows = [json.loads(l) for l in open(ROOT / 'eval/probes/spec_conformance.jsonl')]
    rows = [r for r in rows if r['split'] == 'test']
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['label'],
              'properties': {'label': {'type': 'string', 'enum': list(opts)}}}
    correct, lat, degenerate = 0, [], 0
    for r in rows:
        o = '\n'.join(f'- {k}: {v}' for k, v in opts.items())
        text, fin, _, dt = chat(url, model, f'Classify. Question: {q}\nOptions:\n{o}\n\nInput:\n<<<\n{r["text"]}\n>>>',
                                schema, 512)
        lat.append(dt)
        degenerate += fin == 'length'
        try:
            correct += json.loads(text)['label'] == r['label']
        except (ValueError, KeyError, TypeError):
            pass
    return {'judge_acc': correct / len(rows), 'judge_p50_s': statistics.median(lat), 'judge_degenerate': degenerate}


def bench_tests(url, model, fmt='fenced', repeats=1):
    from aa.quality import parse_fenced_files
    tmpl = (ROOT / 'aa/prompts/oracle_local.md').read_text()
    if fmt == 'json':
        tmpl = tmpl[:tmpl.index('Output format (plain text')] + 'Return the JSON object required by the output schema.'
    valid = degenerate = parse_fail = 0
    lat, toks = [], []
    for name, spec, ref in SPECS * repeats:
        prompt = (tmpl.replace('$prompt', f'Add {spec} to mod.py.').replace('$acceptance', f'- {spec}')
                  .replace('$owner_answers', '')
                  .replace('$context', f'All tracked files:\nmod.py\ntests/test_mod.py\n\n--- mod.py\n{BASE}\n\n'
                                       f'--- tests/test_mod.py (example test)\n{EXAMPLE_TEST}'))
        text, fin, n, dt = chat(url, model, prompt, LOCAL_ORACLE_SCHEMA if fmt == 'json' else None, OPTS.get('max_tokens', 4096))
        lat.append(dt)
        toks.append(n)
        if fin == 'length':
            degenerate += 1
            continue
        try:
            out = json.loads(text) if fmt == 'json' else {'files': parse_fenced_files(text)[0]}
            files = [f for f in out['files'] if f['path'].endswith('.py')]
            for f in files:
                ast.parse(f['content'])
        except (ValueError, KeyError, TypeError, SyntaxError):
            parse_fail += 1
            continue
        if not files:
            parse_fail += 1
            continue
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / 'tests').mkdir()
            for f in files:
                p = d / Path(f['path']).name if '/' not in f['path'] else d / f['path']
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(f['content'])
            rels = [str((d / (f['path'] if '/' in f['path'] else Path(f['path']).name)).relative_to(d)) for f in files]

            def run(src):
                (d / 'mod.py').write_text(src)
                return max(subprocess.run(['python3', '-m', 'unittest', r], cwd=d, capture_output=True, text=True,
                                          timeout=60).returncode for r in rels)
            fails_on_base = run(BASE) != 0
            passes_on_ref = run(BASE + '\n\n' + ref) == 0
        valid += fails_on_base and passes_on_ref
    n = len(SPECS) * repeats
    return {'tests_n': n, 'tests_valid': valid / n, 'tests_parse_fail': parse_fail, 'tests_degenerate': degenerate,
            'tests_p50_s': statistics.median(lat), 'tests_out_tokens_p50': statistics.median(toks)}


def bench_speed(url, model):
    rates = []
    for _ in range(3):
        _, _, n, dt = chat(url, model, 'Write a detailed 600-word technical explanation of how B-trees work.', None, 900)
        rates.append(n / dt)
    return {'decode_tok_s': statistics.median(rates)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--label', required=True)
    ap.add_argument('--url', default='http://127.0.0.1:8100')
    ap.add_argument('--model', default='gemma-4-31b')
    ap.add_argument('--format', default='fenced', choices=['fenced', 'json'])
    ap.add_argument('--sampling', default='{"temperature": 0.2}')
    ap.add_argument('--chat-kwargs', default='{}')
    ap.add_argument('--no-rep-detect', action='store_true')
    ap.add_argument('--repeats', type=int, default=2)
    ap.add_argument('--max-tokens', type=int, default=4096)
    a = ap.parse_args()
    OPTS.update(sampling=json.loads(a.sampling), chat_template_kwargs=json.loads(a.chat_kwargs),
                rep_detect=not a.no_rep_detect, max_tokens=a.max_tokens)
    res = {'label': a.label, 'ts': time.strftime('%Y-%m-%d %H:%M'), 'format': a.format, **OPTS}
    res.update(bench_speed(a.url, a.model))
    res.update(bench_judge(a.url, a.model))
    res.update(bench_tests(a.url, a.model, a.format, a.repeats))
    print(json.dumps(res))
    with open(ROOT / 'eval/results/local-llm-bench.jsonl', 'a') as fh:
        fh.write(json.dumps(res) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
