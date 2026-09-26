"""Plan or execute opt-in project trials. Plans make zero model calls."""
from __future__ import annotations
import argparse, json, os, random, signal, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.ho01_records import fingerprint
from tools.ho01_round import safe_id, POLICIES
from tools.ho02_projects import catalog
from tools.ho02_support import atomic, digest, event, validate_review
from tools.ho02_project_run import run_project


def plan(name, repeats=5, seed=260927, mode='routed'):
    safe_id(name)
    if type(repeats) is not int or not 1<=repeats<=10 or mode not in ('routed','bounded'): raise ValueError('invalid repeats/mode')
    rng=random.Random(seed); ps=catalog(); trials=[]
    for repeat in range(1,repeats+1):
        shuffled=ps[:];rng.shuffle(shuffled)
        for p in shuffled:
            arms=['minimal','full'];rng.shuffle(arms)
            for arm in arms: trials.append({'id':f'{name}-{repeat:02d}-{p["id"]}-{arm}', 'project':p['id'],'policy':arm,'repeat':repeat})
    return {'schema_version':1,'name':name,'repeats':repeats,'seed':seed,'mode':mode,'trials':trials,
        'maximum_task_runs':sum(len(p['stages']) for p in ps)*2*repeats,
        'catalog_sha256':digest(ps),'source_fingerprint':fingerprint(ROOT),
        'policy_hashes':{p:digest(POLICIES[p]) for p in ('minimal','full')}}


def validate(plan_data):
    expected=plan(plan_data['name'],plan_data['repeats'],plan_data['seed'],plan_data['mode'])
    if expected!=plan_data: raise ValueError('plan changed or source/catalog no longer pinned')


def execute(plan_data, out, timeout=3600, resume=False):
    validate(plan_data); out=Path(out).resolve()
    if out.is_relative_to(ROOT): raise ValueError('run outputs must be private and outside this repository')
    if out.exists() and not resume: raise FileExistsError('explicit resume required')
    out.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (out/'round.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        receipt=out/'plan.json'
        if receipt.exists() and json.loads(receipt.read_text())!=plan_data: raise ValueError('another plan owns this output')
        atomic(receipt,plan_data)
        for trial in plan_data['trials']:
            directory=out/trial['id']
            if (directory/'result.json').exists():
                # run_project will validate its manifest even when it already finished.
                p=next(p for p in catalog() if p['id']==trial['project'])
                run_project(p,directory,trial['policy'],plan_data['mode'],resume=True)
                continue
            event(out/'dispatch.jsonl','dispatch_start',trial=trial['id'],resumed=directory.exists())
            command=[sys.executable,str(Path(__file__).resolve()),'trial','--project',trial['project'],
                     '--policy',trial['policy'],'--mode',plan_data['mode'],'--out',str(directory),
                     '--timeout',str(timeout-30)]
            if directory.exists(): command.append('--resume')
            with (out/(trial['id']+'.log')).open('ab') as log:
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                expired=False
                try: code=child.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    expired=True;os.killpg(child.pid,signal.SIGKILL);code=child.wait()
                except BaseException:
                    try: os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError: pass
                    child.wait();raise
            event(out/'dispatch.jsonl','dispatch_end',trial=trial['id'],returncode=code,timeout=expired)
            if code or expired:
                # Do not silently erase or automatically rerun expensive broken attempts.
                raise RuntimeError('trial interrupted; preserve this output and use explicit resume: '+trial['id'])


def main():
    ap=argparse.ArgumentParser(description=__doc__);sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('plan');p.add_argument('--name',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--repeats',type=int,default=5);p.add_argument('--seed',type=int,default=260927);p.add_argument('--mode',choices=['routed','bounded'],default='routed')
    p=sub.add_parser('execute');p.add_argument('--plan',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--resume',action='store_true');p.add_argument('--timeout',type=int,default=3600)
    p=sub.add_parser('trial');p.add_argument('--project',required=True);p.add_argument('--policy',choices=sorted(POLICIES),required=True);p.add_argument('--mode',choices=['routed','bounded'],default='routed');p.add_argument('--out',type=Path,required=True);p.add_argument('--resume',action='store_true');p.add_argument('--timeout',type=int,default=1800)
    p=sub.add_parser('review');p.add_argument('--file',type=Path,required=True);p.add_argument('--snapshot',required=True)
    a=ap.parse_args()
    if a.command=='plan':
        if a.out.exists(): raise FileExistsError('do not overwrite a preregistered plan')
        result=plan(a.name,a.repeats,a.seed,a.mode);atomic(a.out,result);print(result['maximum_task_runs'])
    elif a.command=='execute':
        if not 60<=a.timeout<=7200: raise ValueError('timeout must be 60..7200 seconds')
        execute(json.loads(a.plan.read_text()),a.out,a.timeout,a.resume)
    elif a.command=='trial':
        projects=[p for p in catalog() if p['id']==a.project]
        if len(projects)!=1: raise ValueError('unknown project')
        result=run_project(projects[0],a.out,a.policy,a.mode,resume=a.resume,timeout=a.timeout)
        if result.get('incomplete'): raise SystemExit(2)
    else: validate_review(json.loads(a.file.read_text()),a.snapshot);print('review structure and snapshot match; judgments remain reviewer assertions')

if __name__=='__main__':main()
