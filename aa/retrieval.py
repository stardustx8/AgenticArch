"""Plain BM25 file retrieval over repository contents (no model).

Measured 2026-09-26 on 100 real commits of pallets/click (commit message -> files it edited):
BM25 over contents recall@10 0.63, SemIf on paths 0.50, SemIf on paths + file head 0.40,
path keywords 0.28; SemIf re-ranking a BM25 shortlist did not help (eval/PROBES.md).
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

TOKEN = re.compile(r'[a-z_][a-z0-9_]{2,}')
MAX_BYTES = 200_000


def tokens(text: str) -> list[str]:
    return TOKEN.findall(text.lower())


def bm25_rank(query: str, root: Path, paths: list[str], k: int) -> list[str]:
    """Top-k paths by BM25 of the query against each file's text (binary/huge files skipped)."""
    docs: dict[str, list[str]] = {}
    for p in paths:
        f = root / p
        try:
            data = f.read_bytes()
        except OSError:
            continue
        if len(data) > MAX_BYTES or b'\0' in data[:4096]:
            continue
        docs[p] = tokens(p + '\n' + data.decode('utf-8', 'ignore'))
    if not docs:
        return []
    q = tokens(query)
    avg = sum(map(len, docs.values())) / len(docs)
    df = Counter(t for ts in docs.values() for t in set(ts))
    n = len(docs)

    def score(ts: list[str]) -> float:
        tf = Counter(ts)
        return sum(math.log(1 + (n - df[t] + .5) / (df[t] + .5)) * tf[t] * 2.2 /
                   (tf[t] + 1.2 * (0.25 + 0.75 * len(ts) / avg)) for t in q if t in tf)
    scored = sorted(docs, key=lambda p: -score(docs[p]))
    return scored[:k]
