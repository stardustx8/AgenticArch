#!/usr/bin/env python3
"""Create an immutable paired lab plan, or explicitly execute that plan.

Planning makes no model/CLI calls. Execution invokes existing subscription-only
lab workers. Independent task/repeat blocks run in parallel; both policy arms
within a block run sequentially in randomized order. Every trial has its own
variant and directory, so lab.py's latest-result view cannot erase repeats.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.ho01_records import fingerprint

MINIMAL={s:{'enabled':False} for s in ('oracle_tests','best_of_2','spec_check','failure_triage')}
POLICIES={
    'minimal':MINIMAL,
    'full':{},
    'twins':{'ideas':{'defect_twins':True}},
    'context':{'harness_opt':{'balanced_diffs':True,'focused_failures':True}},
    'stop':{'harness_opt':{'claude_stop_checks':True}},
    'minimal-context':MINIMAL | {'harness_opt':{'balanced_diffs':True,'focused_failures':True}},
    'no-oracle':{'oracle_tests':{'enabled':False}},
    'no-race':{'best_of_2':{'enabled':False}},
    'no-spec':{'spec_check':{'enabled':False}},
    'no-triage':{'failure_triage':{'enabled':False}},
}


def safe_id(value: str) -> str:
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',value):
        raise ValueError(f'invalid identifier: {value!r}')
    return value


def build_plan(tasks: list[str], policies: list[str], repeats: int, seed: int, name: str) -> dict:
    safe_id(name)
    if not tasks or len(set(tasks))!=len(tasks) or not 1<=repeats<=20:
        raise ValueError('unique nonempty tasks and 1..20 repeats required')
    if len(policies)<2 or len(set(policies))!=len(policies) or any(p not in POLICIES for p in policies):
        raise ValueError('at least two distinct registered policies required')
    for task in tasks: safe_id(task)
    rng=random.Random(seed)
    blocks=[]
    for repeat in range(1,repeats+1):
        order=sorted(tasks); rng.shuffle(order)
        for task in order:
            arms=policies[:]; rng.shuffle(arms)
            blocks.append({'task':task,'repeat':repeat,'arms':[
                {'policy':p,'variant':f'{name}-{repeat:02d}-{task}-{p}',
                 'flags':POLICIES[p] | {'harness_opt':POLICIES[p].get('harness_opt',{}) | {'gate_shadow':True}}}
                for p in arms]})
    return {'schema_version':1,'name':name,'seed':seed,'blocks':blocks,
            'task_runs':len(tasks)*len(policies)*repeats,'policies':policies,'repeats':repeats,
            'prediction':'Record the pre-run prediction and stop/decision rule in EXPERIMENTS.md.'}


def validate_plan(plan: dict, root: Path) -> None:
    blocks=plan['blocks']; tasks=sorted({b['task'] for b in blocks})
    expected=build_plan(tasks,plan['policies'],plan['repeats'],plan['seed'],plan['name'])
    if blocks!=expected['blocks'] or plan['task_runs']!=expected['task_runs']:
        raise ValueError('plan arms/order/count differ from deterministic registered plan')
    if fingerprint(root)!=plan['source_fingerprint']:
        raise ValueError('source/task files changed after planning')
    for task in tasks:
        if not (root/'eval/lab/tasks'/task/'task.json').is_file():
            raise ValueError('task missing: '+task)


def read_trial(root: Path, arm: dict, task: str) -> dict | None:
    path=root/'eval/lab/results'/f'{arm["variant"]}.jsonl'
    if not path.exists(): return None
    rows=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    if len(rows)!=1 or rows[0].get('task')!=task or rows[0].get('variant')!=arm['variant']:
        raise ValueError('unexpected trial identity or duplicate results')
    return rows[0]


def execute(plan: dict, path: Path, root: Path, parallel: int, timeout: int) -> None:
    validate_plan(plan,root)
    if not 1<=parallel<=4 or not 1<=timeout<=7200:
        raise ValueError('parallel must be 1..4; timeout 1..7200 seconds')
    # mkdir is the atomic no-repeat guard, including concurrent invocations.
    out=path.with_suffix(''); out.mkdir(parents=True,exist_ok=False)
    if any((root/'eval/lab/results'/f'{a["variant"]}.jsonl').exists() or
           (root/'eval/lab/results/runs'/a['variant']).exists()
           for b in plan['blocks'] for a in b['arms']):
        raise ValueError('trial outputs already exist; use a new round name')
    versions={}
    for cli in ('codex','claude','git'):
        try:
            p=subprocess.run([cli,'--version'],capture_output=True,text=True,timeout=10)
            versions[cli]={'returncode':p.returncode,'version':p.stdout.strip()[:300]}
        except (OSError,subprocess.TimeoutExpired) as e:
            versions[cli]={'error':type(e).__name__}
    (out/'execution.json').write_text(json.dumps({'versions':versions,'parallel_blocks':parallel,
                                                 'started_unix':time.time(),'python':sys.version},indent=2))
    def block(b):
        for arm in b['arms']:
            if (out/'STOP').exists(): return
            # Reject mid-round source edits without throwing away completed trials.
            validate_plan(plan,root)
            started=time.monotonic()
            cmd=[sys.executable,'tools/lab.py','--variant',arm['variant'],'--flags',json.dumps(arm['flags']),
                 '--tasks',b['task'],'--parallel','1','--timeout',str(timeout),'--record-v2']
            with (out/(arm['variant']+'.log')).open('x') as log:
                p=subprocess.run(cmd,cwd=root,stdout=log,stderr=subprocess.STDOUT)
            row=read_trial(root,arm,b['task'])
            rec={'task':b['task'],'repeat':b['repeat'],'policy':arm['policy'],'variant':arm['variant'],
                 'external_wall_seconds':time.monotonic()-started,'process_returncode':p.returncode,
                 'result':row,'missing_result':row is None,
                 'costs_observed_completely': bool(row is not None and not row.get('resource_measurements_unknown')
                     and row.get('usage_missing_calls') == 0)}
            (out/(arm['variant']+'.json')).write_text(json.dumps(rec,indent=2)+'\n')
            if p.returncode or row is None or row.get('status')=='ERROR':
                (out/'STOP').touch()  # drain in-flight work; do not silently spend the remaining budget
                return
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        list(pool.map(block,plan['blocks']))
    (out/'completed.json').write_text(json.dumps({'stopped_early':(out/'STOP').exists(),
                                                  'ended_unix':time.time()},indent=2))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    modes=ap.add_mutually_exclusive_group(required=True)
    modes.add_argument('--plan',type=Path); modes.add_argument('--execute',type=Path)
    ap.add_argument('--tasks',default=''); ap.add_argument('--policies',default='minimal,full')
    ap.add_argument('--repeats',type=int,default=3); ap.add_argument('--seed',type=int,default=260926)
    ap.add_argument('--name',default='ho01-r1'); ap.add_argument('--parallel',type=int,default=4)
    ap.add_argument('--timeout',type=int,default=2700)
    a=ap.parse_args()
    if a.plan:
        plan=build_plan(a.tasks.split(','),a.policies.split(','),a.repeats,a.seed,a.name)
        plan['source_fingerprint']=fingerprint(ROOT)
        validate_plan(plan,ROOT)
        a.plan.parent.mkdir(parents=True,exist_ok=True)
        with a.plan.open('x') as f: json.dump(plan,f,indent=2); f.write('\n')
        print(f'Planned {plan["task_runs"]} task-runs; no workers started: {a.plan}')
    else:
        execute(json.loads(a.execute.read_text()),a.execute,ROOT,a.parallel,a.timeout)
    return 0

if __name__=='__main__':
    raise SystemExit(main())
