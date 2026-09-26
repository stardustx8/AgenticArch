"""Context selection benchmark: which files does a change need, given its description?

Ground truth: past commits of pallets/click. Query = commit message (file names masked),
relevant = the .py/.rst/.md files the commit modified that existed at its parent.
Candidates = all such files at the parent commit. Methods rank candidates; metrics are
recall@5, recall@10 and MRR of the first relevant file. Dev/test split by commit order.
"""
import json
import math
import random
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
EXT = re.compile(r'\.(py|rst|md)$')
# usage: python3 tools/bench_context.py <clone of github.com/pallets/click> [n_commits] [out.json]
REPO = Path(sys.argv[1]) if len(sys.argv) > 1 else Path('ctx-click')
N = int(sys.argv[2]) if len(sys.argv) > 2 else 100
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else Path('ctx_bench.json')


def git(*a):
    return subprocess.run(['git', '-C', str(REPO), *a], capture_output=True, text=True, check=True).stdout


def sample_commits():
    out = []
    for line in git('log', '--no-merges', '--format=%H', '-n', '2500').split():
        files = [f for f in git('diff-tree', '--no-commit-id', '--name-status', '-r', line).splitlines()]
        mod = [f.split('\t', 1)[1] for f in files if f.startswith('M\t') and EXT.search(f)]
        if not 1 <= len(mod) <= 4 or len(files) > 8:
            continue
        mod = [f for f in mod if 'CHANGES' not in f]           # changelog edits are trivially guessable
        if not mod:
            continue
        msg = git('log', '-1', '--format=%B', line).strip()
        msg = '\n'.join(l for l in msg.splitlines() if not re.match(r'(Co-authored-by|Signed-off-by):', l, re.I))
        if len(msg) < 25:
            continue
        out.append({'sha': line, 'msg': msg, 'gold': mod})
    random.Random(7).shuffle(out)
    return out[:N]


def mask(msg, cands):
    names = {Path(c).name for c in cands} | {Path(c).stem for c in cands if len(Path(c).stem) > 3}
    for n in sorted(names, key=len, reverse=True):
        msg = re.sub(r'\b' + re.escape(n) + r'\b', '<file>', msg)
    return msg[:1500]


def tokens(s):
    return re.findall(r'[a-z_][a-z0-9_]{2,}', s.lower())


def bm25(query, docs):
    tq = tokens(query)
    toks = {k: tokens(v) for k, v in docs.items()}
    avg = sum(map(len, toks.values())) / max(1, len(toks))
    df = Counter(t for ts in toks.values() for t in set(ts))
    n = len(toks)
    score = {}
    for k, ts in toks.items():
        tf = Counter(ts)
        s = 0.0
        for t in tq:
            if t in tf:
                idf = math.log(1 + (n - df[t] + .5) / (df[t] + .5))
                s += idf * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * len(ts) / avg))
        score[k] = s
    return score


def metrics(ranked, gold):
    first = next((i for i, c in enumerate(ranked) if c in gold), None)
    return {'r5': len(set(ranked[:5]) & set(gold)) / len(gold), 'r10': len(set(ranked[:10]) & set(gold)) / len(gold),
            'mrr': 0 if first is None else 1 / (first + 1)}


def main():
    from aa import config
    from aa.db import DB
    from aa.semif import SemIf
    s = SemIf(config.load(), DB(':memory:'))
    assert s.available(), 'SemIf not running'
    q = 'Does this change need to edit this file?'
    opts = {'yes': 'Yes, the change must edit this file.', 'no': 'No, this file is unrelated to the change.'}
    commits = sample_commits()
    rows = []
    t0 = time.time()
    for i, c in enumerate(commits):
        parent = c['sha'] + '^'
        cands = [f for f in git('ls-tree', '-r', '--name-only', parent).splitlines() if EXT.search(f)]
        gold = [g for g in c['gold'] if g in cands]
        if not gold:
            continue
        query = mask(c['msg'], cands)
        content = {f: git('show', f'{parent}:{f}') for f in cands}
        head = {f: '\n'.join(v.splitlines()[:40]) for f, v in content.items()}
        sc = {}
        sc['random'] = {f: random.Random(i).random() for f in cands}
        sc['keyword_path'] = {f: sum(w in f.lower() for w in tokens(query)) for f in cands}
        sc['bm25_content'] = bm25(query, content)
        sc['semif_path'] = {f: s._probs(f'Change: {query}\n\nFile: {f}', q, opts)['yes'] for f in cands}
        sc['semif_head'] = {f: s._probs(f'Change: {query}\n\nFile: {f}\n{head[f]}'[:6000], q, opts)['yes'] for f in cands}
        # simple fusion: BM25 shortlist, SemIf (with file head) re-ranks the top 15
        b = sorted(cands, key=lambda f: -sc['bm25_content'][f])
        short = b[:15]
        sc['bm25_then_semif'] = {f: (2 + sc['semif_head'][f]) if f in short else -b.index(f) for f in cands}
        row = {'sha': c['sha'][:10], 'split': 'dev' if i % 2 == 0 else 'test', 'n_cands': len(cands), 'gold': gold}
        for m, score in sc.items():
            ranked = sorted(cands, key=lambda f: -score[f])
            row[m] = metrics(ranked, gold)
        rows.append(row)
        print(f'{i + 1}/{len(commits)} {time.time() - t0:.0f}s', flush=True)
    json.dump(rows, open(OUT, 'w'), indent=1)
    methods = [k for k in rows[0] if isinstance(rows[0][k], dict)]
    for split in ('dev', 'test', 'all'):
        rs = [r for r in rows if split == 'all' or r['split'] == split]
        print(f'\n{split} (n={len(rs)}, candidates median {sorted(r["n_cands"] for r in rs)[len(rs) // 2]})')
        for m in methods:
            print(f'  {m:16} r@5 {sum(r[m]["r5"] for r in rs) / len(rs):.2f}  r@10 {sum(r[m]["r10"] for r in rs) / len(rs):.2f}'
                  f'  mrr {sum(r[m]["mrr"] for r in rs) / len(rs):.2f}')


if __name__ == '__main__':
    main()
