#!/usr/bin/env python3
"""Benchmark semantic deciders (CLM, SemIf, Codex) on eval/decisions/tier.jsonl.

For every backend, several question/option phrasings are scored. The phrasing with
the lowest error cost on the dev split is selected; the report shows its test-split
result (no tuning on test). Cost weights the owner's risk: under-tiering is worse
than over-tiering, and missing a tough (Pro) task is worst.

  python3 tools/eval_decisions.py --backends clm,semif          # local only
  python3 tools/eval_decisions.py --backends clm,semif,codex    # + Codex Luna baseline (uses quota)
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aa.decisions import (CHOSEN, PEER_OPTIONS, PEER_QUESTIONS, TIER_OPTIONS,  # noqa: E402
                          TIER_QUESTIONS, TIERS)


def cost(label: str, pred: str | None) -> float:
    if pred is None:
        return 1.0                      # abstention: the owner is asked
    d = TIERS.index(pred) - TIERS.index(label)
    if d == 0:
        return 0.0
    if label == 'tough' and d < 0:
        return 5.0                      # missed a mandatory Pro case
    if d < 0:
        return 2.0 * -d                 # under-tiered: likely failure and rework
    return 1.0 * d                      # over-tiered: wasted quota


# ----------------------------------------------------------------------- backends
def clm_score(rows, options, question, url='http://127.0.0.1:8700'):
    out = {}
    for r in rows:
        body = json.dumps({'model': 'clm-latest', 'state': r['text'], 'questions': {'q': {
            'type': 'choice', 'instructions': question, 'criteria': options}}}).encode()
        req = urllib.request.Request(url + '/v1/systemone', data=body,
                                     headers={'Content-Type': 'application/json'})
        t0 = time.perf_counter()
        with urllib.request.urlopen(req, timeout=60) as resp:
            ans = json.load(resp)['answers']['q']
        out[r['id']] = (ans['probabilities'], time.perf_counter() - t0)
    return out


SEMIF_DIR = Path('~/.local/share/agenticarch/semif').expanduser()


def semif_batch(jobs: list[tuple[str, dict, dict, str]], scratch: Path) -> dict:
    """jobs: (job_id, row, options, question) -> {job_id: (probs, seconds)} in ONE container run."""
    inp, outd = scratch / 'in', scratch / 'out'
    inp.mkdir(parents=True, exist_ok=True)
    outd.mkdir(parents=True, exist_ok=True)
    with open(inp / 'jobs.jsonl', 'w') as fh:
        for jid, row, options, question in jobs:
            fh.write(json.dumps({'id': jid, 'state': row['text'], 'question': question,
                                 'options': [{'id': k, 'description': v} for k, v in options.items()]}) + '\n')
    cmd = ['docker', 'run', '--rm', '--gpus', 'all', '--network', 'none', '--cap-drop', 'ALL',
           '--security-opt', 'no-new-privileges', '--read-only', '--tmpfs', '/tmp:rw,nosuid,size=4g',
           '-e', 'HOME=/tmp', '-e', 'HF_HUB_OFFLINE=1', '-e', 'TRANSFORMERS_OFFLINE=1',
           '-e', 'PYTHONPATH=/opt/semif/src', '-v', f'{SEMIF_DIR}/cache:/cache:rw',
           '-e', 'TRITON_CACHE_DIR=/cache/triton', '-e', 'TORCHINDUCTOR_CACHE_DIR=/cache/torchinductor',
           '-v', f'{SEMIF_DIR}/qwen3.5-4b:/models/qwen3.5-4b:ro', '-v', f'{SEMIF_DIR}/src:/opt/semif:ro',
           '-v', f'{inp}:/inputs:ro', '-v', f'{outd}:/outputs:rw', 'ai-lab/private-semif:2026-09-21',
           '-m', 'semif_phase1.cli', '--mode', 'direct', '--model', '/models/qwen3.5-4b',
           '--revision', 'local-Qwen3.5-4B', '--input', '/inputs/jobs.jsonl', '--output', '/outputs/r.jsonl']
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    res = {}
    for line in open(outd / 'r.jsonl'):
        d = json.loads(line)
        res[d['id']] = (dict(zip(d['option_ids'], d['probabilities'])), d['forward_seconds'])
    return res


CODEX_SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['tier', 'peer'],
                'properties': {'tier': {'type': 'string', 'enum': TIERS},
                               'peer': {'type': 'string', 'enum': ['astra', 'opus']}}}


def codex_score(rows, guide: str, lane_name='luna_high'):
    from aa import config
    from aa.workers import LANES, Workers
    cfg = config.load()
    w = Workers(cfg)
    lane = LANES[lane_name]
    scratch = Path('/tmp') if not cfg.state_dir.exists() else cfg.state_dir / 'eval-scratch'
    scratch.mkdir(parents=True, exist_ok=True)

    def one(r):
        prompt = (f'Classify this request. Do not run commands or read files.\n\n{guide}\n\n'
                  f'Request:\n<<<\n{r["text"]}\n>>>\n\nReturn the tier and, as if it were medium_tough, '
                  'the better peer (astra for backend/systems/data/infra/debugging, opus for '
                  'frontend/UI/visual/product/writing).')
        res = w.execute(lane, prompt, scratch, write=False, schema=CODEX_SCHEMA, log_name=f'eval-{r["id"]}')
        return r['id'], (res.structured if res.ok else None, res.seconds)

    with ThreadPoolExecutor(4) as pool:
        return dict(pool.map(one, rows))


# ------------------------------------------------------------------------ metrics
def conf(probs: dict) -> float:
    v = sorted(probs.values(), reverse=True)
    return v[0] - sum(v[1:]) / max(1, len(v) - 1)


def tier_metrics(rows, preds: dict) -> dict:
    n = len(rows)
    correct = sum(preds[r['id']] == r['tier'] for r in rows)
    under = sum(preds[r['id']] is not None and TIERS.index(preds[r['id']]) < TIERS.index(r['tier']) for r in rows)
    over = sum(preds[r['id']] is not None and TIERS.index(preds[r['id']]) > TIERS.index(r['tier']) for r in rows)
    tough = [r for r in rows if r['tier'] == 'tough']
    missed = sum(preds[r['id']] != 'tough' for r in tough)
    f1s = []
    for t in TIERS:
        tp = sum(preds[r['id']] == t and r['tier'] == t for r in rows)
        fp = sum(preds[r['id']] == t and r['tier'] != t for r in rows)
        fn = sum(preds[r['id']] != t and r['tier'] == t for r in rows)
        f1s.append(0 if tp == 0 else 2 * tp / (2 * tp + fp + fn))
    confusion = {t: {p: sum(r['tier'] == t and preds[r['id']] == p for r in rows) for p in TIERS}
                 for t in TIERS}
    return {'n': n, 'accuracy': correct / n, 'macro_f1': sum(f1s) / 4, 'under': under / n,
            'over': over / n, 'missed_tough': f'{missed}/{len(tough)}',
            'cost': sum(cost(r['tier'], preds[r['id']]) for r in rows) / n, 'confusion': confusion}


def argmax(p: dict) -> str:
    return max(p, key=p.get)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--backends', default='clm,semif')
    ap.add_argument('--data', default=str(ROOT / 'eval/decisions/tier.jsonl'))
    ap.add_argument('--out', default=str(ROOT / 'eval/results'))
    ap.add_argument('--codex-cache', help='reuse Codex results from an earlier *-decisions.json')
    ap.add_argument('--fixed-variants', action='store_true',
                    help='use the wordings in aa.decisions.CHOSEN instead of selecting (for holdout files)')
    ap.add_argument('--select-on', default='dev', help='split used to pick wordings (dev; "all" for a holdout file)')
    ap.add_argument('--report-on', default='test', help='split to report (test; "all" for a holdout file)')
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.data)]
    tier_rows = [r for r in rows if r['tier']]
    peer_rows = [r for r in rows if r['peer']]
    backends = a.backends.split(',')
    scratch = Path('/tmp/claude-eval-' + str(int(time.time())))
    raw: dict = {}      # backend -> task -> variant -> {row_id: probs}
    lat: dict = {}

    variants_t = [(o, q) for o in TIER_OPTIONS for q in TIER_QUESTIONS]
    variants_p = [(o, q) for o in PEER_OPTIONS for q in PEER_QUESTIONS]

    if 'clm' in backends:
        raw['clm'] = {'tier': {}, 'peer': {}}
        secs = []
        for o, q in variants_t:
            res = clm_score(tier_rows, TIER_OPTIONS[o], TIER_QUESTIONS[q])
            raw['clm']['tier'][f'{o}/{q}'] = {k: v[0] for k, v in res.items()}
            secs += [v[1] for v in res.values()]
        for o, q in variants_p:
            res = clm_score(peer_rows, PEER_OPTIONS[o], PEER_QUESTIONS[q])
            raw['clm']['peer'][f'{o}/{q}'] = {k: v[0] for k, v in res.items()}
        lat['clm'] = statistics.median(secs)
        print('clm done', file=sys.stderr)

    if 'semif' in backends:
        jobs = [(f'tier|{o}/{q}|{r["id"]}', r, TIER_OPTIONS[o], TIER_QUESTIONS[q])
                for o, q in variants_t for r in tier_rows]
        jobs += [(f'peer|{o}/{q}|{r["id"]}', r, PEER_OPTIONS[o], PEER_QUESTIONS[q])
                 for o, q in variants_p for r in peer_rows]
        res = semif_batch(jobs, scratch / 'semif')
        raw['semif'] = {'tier': {}, 'peer': {}}
        for jid, (probs, _) in res.items():
            task, var, rid = jid.split('|')
            raw['semif'][task].setdefault(var, {})[rid] = probs
        lat['semif'] = statistics.median(v[1] for v in res.values())
        print('semif done', file=sys.stderr)

    if 'rules' in backends:
        from aa.rules import peer_of, tier_of
        raw['rules'] = {'tier': {'keywords': {r['id']: {t: float(t == tier_of(r['text'])) for t in TIERS}
                                              for r in tier_rows}},
                        'peer': {'keywords': {r['id']: {p: float(p == peer_of(r['text'])) for p in ('astra', 'opus')}
                                              for r in peer_rows}}}
        lat['rules'] = 0.0

    codex = None
    if a.codex_cache:
        codex = json.loads(Path(a.codex_cache).read_text())['codex']
        lat['codex'] = statistics.median(v[1] for v in codex.values())
    elif 'codex' in backends:
        guide = (ROOT / 'eval/README.md').read_text().split('## Labelling guide', 1)[1]
        test_rows = [r for r in rows if a.report_on == 'all' or r['split'] == a.report_on]
        codex = codex_score(test_rows, guide)
        lat['codex'] = statistics.median(v[1] for v in codex.values())
        print('codex done', file=sys.stderr)

    # ------------------------------------------------------------ selection + report
    report: dict = {'date': time.strftime('%Y-%m-%d %H:%M'), 'n_tier': len(tier_rows),
                    'n_peer': len(peer_rows), 'latency_median_s': lat, 'tier': {}, 'peer': {}}
    sel = lambda rs, sp: [r for r in rs if sp == 'all' or r['split'] == sp]
    dev_t, test_t = sel(tier_rows, a.select_on), sel(tier_rows, a.report_on)
    dev_p, test_p = sel(peer_rows, a.select_on), sel(peer_rows, a.report_on)
    for b, tasks in raw.items():
        scored = []
        for var, probs in tasks['tier'].items():
            preds = {k: argmax(v) for k, v in probs.items()}
            scored.append((tier_metrics(dev_t, preds)['cost'], var))
        best = min(scored)[1]
        if a.fixed_variants and b in CHOSEN:
            best = '/'.join(CHOSEN[b]['tier'])
        probs = tasks['tier'][best]
        preds = {k: argmax(v) for k, v in probs.items()}
        entry = {'variant': best, 'dev': tier_metrics(dev_t, preds), 'test': tier_metrics(test_t, preds),
                 'all_variants_dev_cost': {v: round(c, 3) for c, v in sorted(scored)}}
        # Abstention sweep on test: below threshold -> owner asked.
        sweep = {}
        for th in (0.0, 0.2, 0.4, 0.6):
            p2 = {k: (argmax(v) if conf(v) >= th else None) for k, v in probs.items()}
            m = tier_metrics(test_t, p2)
            covered = [r for r in test_t if p2[r['id']] is not None]
            sweep[th] = {'coverage': len(covered) / len(test_t),
                         'acc_when_answering': (sum(p2[r['id']] == r['tier'] for r in covered) / len(covered)) if covered else None,
                         'cost': m['cost']}
        entry['abstention_test'] = sweep
        if any('tricky' in r for r in test_t):
            for flag in (True, False):
                sub = [r for r in test_t if r.get('tricky') is flag]
                entry[f'acc_tricky_{flag}'] = sum(preds[r['id']] == r['tier'] for r in sub) / len(sub)
        report['tier'][b] = entry
        pscored = []
        for var, pr in tasks['peer'].items():
            acc = sum(argmax(pr[r['id']]) == r['peer'] for r in dev_p) / len(dev_p)
            pscored.append((-acc, var))
        pbest = min(pscored)[1]
        if a.fixed_variants and b in CHOSEN:
            pbest = '/'.join(CHOSEN[b]['peer'])
        pr = tasks['peer'][pbest]
        report['peer'][b] = {'variant': pbest,
                             'dev_acc': sum(argmax(pr[r['id']]) == r['peer'] for r in dev_p) / len(dev_p),
                             'test_acc': sum(argmax(pr[r['id']]) == r['peer'] for r in test_p) / len(test_p)}
    if codex is not None:
        cpreds = {k: (v[0] or {}).get('tier') for k, v in codex.items()}
        report['tier']['codex'] = {'variant': 'luna_high+guide', 'test': tier_metrics(test_t, cpreds)}
        if any('tricky' in r for r in test_t):
            for flag in (True, False):
                sub = [r for r in test_t if r.get('tricky') is flag]
                report['tier']['codex'][f'acc_tricky_{flag}'] = sum(cpreds[r['id']] == r['tier'] for r in sub) / len(sub)
        report['peer']['codex'] = {'variant': 'luna_high+guide',
                                   'test_acc': sum((codex[r['id']][0] or {}).get('peer') == r['peer']
                                                   for r in test_p) / len(test_p)}
        # The production rule: Codex + decider agree -> use; disagree -> ask owner.
        report['combined'] = {}
        for b in raw:
            probs = raw[b]['tier'][report['tier'][b]['variant']]
            for th in (0.0, 0.2, 0.4):
                agree = asked = right = 0
                for r in test_t:
                    c = cpreds[r['id']]
                    p = probs[r['id']]
                    m = argmax(p) if conf(p) >= th else None
                    if m is None or m == c:
                        agree += 1
                        right += (c == r['tier'])
                    else:
                        asked += 1
                report['combined'][f'{b}@{th}'] = {'owner_asked': asked / len(test_t),
                                                   'acc_when_auto': right / agree if agree else None}
    majority = {r['id']: 'bounded' for r in tier_rows}
    report['tier']['always_bounded'] = {'variant': '-', 'test': tier_metrics(test_t, majority)}

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d-%H%M')
    (out / f'{stamp}-decisions.json').write_text(json.dumps({'report': report, 'raw': raw,
                                                             'codex': codex}, indent=1, default=str))
    md = render(report)
    (out / f'{stamp}-decisions.md').write_text(md)
    print(md)
    return 0


def render(rep: dict) -> str:
    L = [f'# Decision benchmark {rep["date"]}', '',
         f'{rep["n_tier"]} tier rows, {rep["n_peer"]} peer rows; wording chosen on dev, reported on test.', '',
         '## Tier (test split)', '',
         '| Backend | Wording | Accuracy | Macro-F1 | Under-tier | Over-tier | Missed tough | Cost/row |',
         '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for b, e in rep['tier'].items():
        m = e['test']
        L.append(f'| {b} | {e["variant"]} | {m["accuracy"]:.0%} | {m["macro_f1"]:.2f} | {m["under"]:.0%} | '
                 f'{m["over"]:.0%} | {m["missed_tough"]} | {m["cost"]:.2f} |')
    tricky = [(b, e) for b, e in rep['tier'].items() if 'acc_tricky_True' in e]
    if tricky:
        L += ['', '| Backend | Accuracy on misleading (tricky) rows | on normal rows |', '| --- | --- | --- |']
        L += [f'| {b} | {e["acc_tricky_True"]:.0%} | {e["acc_tricky_False"]:.0%} |' for b, e in tricky]
    L += ['', 'Cost: 0 correct, 1 per tier over, 2 per tier under, 5 for a tough task routed lower, 1 for asking the owner.', '']
    for b, e in rep['tier'].items():
        if 'confusion' in e['test']:
            L += [f'### {b} confusion (rows = label, cols = prediction)', '',
                  '| | ' + ' | '.join(TIERS) + ' |', '| --- |' + ' --- |' * 4]
            for t, row in e['test']['confusion'].items():
                L.append(f'| {t} | ' + ' | '.join(str(row[p]) for p in TIERS) + ' |')
            L.append('')
        if 'abstention_test' in e:
            L.append(f'{b} abstention (confidence threshold -> coverage, accuracy when answering, cost): ' +
                     '; '.join(f'{th}: {v["coverage"]:.0%}, {v["acc_when_answering"] if v["acc_when_answering"] is None else format(v["acc_when_answering"], ".0%")}, {v["cost"]:.2f}'
                               for th, v in e['abstention_test'].items()))
            L.append('')
    L += ['## Peer model (astra vs opus)', '', '| Backend | Wording | Dev acc | Test acc |', '| --- | --- | --- | --- |']
    for b, e in rep['peer'].items():
        L.append(f'| {b} | {e["variant"]} | {e.get("dev_acc", float("nan")):.0%} | {e["test_acc"]:.0%} |')
    if 'combined' in rep:
        L += ['', '## Production rule: Codex + decider, owner asked on disagreement (test)', '',
              '| Decider@threshold | Owner asked | Accuracy when automatic |', '| --- | --- | --- |']
        for k, v in rep['combined'].items():
            L.append(f'| {k} | {v["owner_asked"]:.0%} | {v["acc_when_auto"]:.0%} |')
    L += ['', 'Median latency per decision (s): ' + ', '.join(f'{k} {v:.3f}' for k, v in rep['latency_median_s'].items())]
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    sys.exit(main())
