"""Calibration-gated hard/ultra lab. Planning, auditing and reporting make zero model calls."""
from __future__ import annotations
import argparse
import inspect
import json
import math
import os
from pathlib import Path
import random
import signal
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aa.workers import Workers
from tools.ho01_records import fingerprint
from tools.ho01_round import POLICIES, safe_id
from tools.ho02_project_run import config_hash, effective_config, run_project
from tools.ho02_support import atomic, digest, event, pending_calls, validate_review
from tools.ho03_projects import catalog
from tools.ho03_support import deadline, verify_handoff

PHASES={'calibration':(14400,[2,6,12]),'upper-diagnostic':(10800,[2,6]),
        'extension':(43200,[2,42]),'routing':(4500,[3])}


def plan(name, phase='calibration', seed=261001):
    safe_id(name)
    if phase not in PHASES or type(seed) is not int:raise ValueError('unknown phase or seed')
    rng=random.Random(seed); projects=catalog(); trials=[]
    groups=[('middle',1),('ultra',1)]
    if phase=='upper-diagnostic':groups=[('ultra',1)]
    if phase=='extension':groups=[('middle',5),('ultra',2)]
    if phase=='routing':groups=[('ultra',1)]
    for difficulty,repeats in groups:
        for repeat in range(1,repeats+1):
            ps=[p for p in projects if p['difficulty']==difficulty];rng.shuffle(ps)
            for p in ps:
                arms=['full'] if phase=='routing' else ['minimal','full'];rng.shuffle(arms)
                for arm in arms:
                    trials.append(dict(id=f'{name}-{repeat:02d}-{p["id"]}-{arm}',project=p['id'],
                                       difficulty=difficulty,cluster=p['cluster'],repeat=repeat,policy=arm,
                                       timeout_s=600 if phase=='routing' else p['budget_seconds']))
    cap,checkpoints=PHASES[phase]
    return dict(schema_version=3,name=name,phase=phase,seed=seed,trials=trials,
                mode='routed' if phase=='routing' else 'bounded',comparison_tier=None if phase=='routing' else 'medium_tough',
                source_fingerprint=fingerprint(ROOT),catalog_sha256=digest(projects),
                effective_config_hashes={a:config_hash(effective_config(a,'unused',isolate_memories=True)) for a in ('minimal','full')},
                maximum_stage_runs=len(trials) if phase=='routing' else len(trials)*2,wall_cap_s=cap,checkpoints=checkpoints,
                injected_worker_faults=False,grading='after_model_trajectory',
                prediction='Middle pooled stage pass is 0.2..0.8; ultra single-worker failure is frequent. These are unmeasured hypotheses.')


def validate(p):
    if p!=plan(p['name'],p['phase'],p['seed']):raise ValueError('plan/source/configuration/catalog changed')


def memory_implementation_available():
    text=inspect.getsource(Workers._codex)
    return all(v in text for v in ('codex_no_memories','features.memories=false',
                                  'memories.use_memories=false','memories.generate_memories=false'))


def read_native_versions():
    cfg=effective_config('full','unused',isolate_memories=True)
    commands={'codex':str(cfg.path('workers','codex')),'claude':str(cfg.path('workers','claude')),'node':'node'}
    versions={}
    for name,cmd in commands.items():
        r=subprocess.run([cmd,'--version'],capture_output=True,text=True,timeout=30,check=True)
        versions[name]=r.stdout.strip() or r.stderr.strip()
        if not versions[name]:raise ValueError('empty CLI version: '+name)
    return versions


def native_audit(a,p):
    if not memory_implementation_available():raise ValueError('native memory implementation is not installed; do not run workers')
    if a.get('source_fingerprint')!=p['source_fingerprint']:raise ValueError('native audit is for another source')
    if not isinstance(a.get('reviewer'),str) or not a['reviewer'].strip():raise ValueError('named native audit required')
    if not isinstance(a.get('evidence'),list) or not a['evidence'] or not all(isinstance(x,str) and x.strip() for x in a['evidence']):raise ValueError('inspectable native audit evidence required')
    for key in ('memory_injection_absent','subscription_auth_unchanged','node_available','cgroup_limits_verified'):
        if a.get(key) is not True:raise ValueError('native preflight not verified: '+key)
    if not isinstance(a.get('cli_versions'),dict) or not all(a['cli_versions'].get(k) for k in ('codex','claude','node')):
        raise ValueError('installed versions must be recorded')
    return digest(a)


def rows(p,root):
    validate(p); projects={x['id']:x for x in catalog()}; result=[]
    for trial in p['trials']:
        path=Path(root)/trial['id']; row=dict(trial,observed=False,first_coverage=0,first_correct=None,
            final_correct=None,trajectory_correct=None,new_protected_violations=0,tainted_stages=0,
            critical_findings=0,critical_reviewed_stages=0,mechanical_handoffs=0,seconds=None,provider_calls=0,usage_by_lane={})
        if not (path/'result.json').exists():result.append(row);continue
        r=json.loads((path/'result.json').read_text()); m=json.loads((path/'manifest.json').read_text()); project=projects[trial['project']]
        expected=dict(source_fingerprint=p['source_fingerprint'],project_hash=digest(project),policy=trial['policy'],
            flags=POLICIES[trial['policy']],mode=p['mode'],comparison_tier=p['comparison_tier'],offline_handoff=True,
            defer_grading=True,routing_only=p['phase']=='routing',timeout_s=trial['timeout_s'],effective_config_sha256=p['effective_config_hashes'][trial['policy']])
        if any(m.get(k)!=v for k,v in expected.items()) or r.get('project')!=trial['project'] or r.get('policy')!=trial['policy']:
            raise ValueError('foreign result/configuration identity')
        stages=r['stages']; n=len(project['stages'])
        if not stages or len(stages)>n or [s['stage'] for s in stages]!=list(range(1,len(stages)+1)):
            raise ValueError('duplicate, absent or reordered stages')
        def passed(s,key):
            g=s.get(key)
            return bool(g and all(g.get(k) is True for k in ('hidden_pass','all_tests_pass','protected_preserved')))
        final=[s['status']=='DONE' and passed(s,'final') for s in stages]
        if any(type(s.get('correct_delivery')) is not bool or s['correct_delivery']!=v for s,v in zip(stages,final)):
            raise ValueError('unsupported completion claim')
        first_seen=sum(s.get('first') is not None for s in stages)
        row.update(observed=True,first_coverage=first_seen/n,first_correct=sum(passed(s,'first') for s in stages)/n if first_seen==n else None,
            final_correct=sum(final)/n,trajectory_correct=int(len(stages)==n and all(final)),
            seconds=r.get('elapsed_since_first_start',r.get('attempt_seconds')),
            unclosed_calls=pending_calls(path/'events.jsonl'))
        row['stage_delta_correct']=sum(bool(s.get('stage_delta_correct')) for s in stages)/n
        row['coding_score_applicable']=p['phase']!='routing'
        row['route_tier']=stages[0]['task'].get('tier')
        if p['phase']=='routing':row.update(final_correct=None,trajectory_correct=None)
        for s in stages:
            grade=s.get('final')
            if grade:
                row['new_protected_violations']+=bool(grade.get('protected_changed_this_stage'))
                row['tainted_stages']+=not grade['protected_preserved']
            if s.get('handoff'):
                row['mechanical_handoffs']+=verify_handoff(path/f'handoff-stage-{s["stage"]}')
            review=path/f'review-stage-{s["stage"]}.json'
            if grade and review.exists():
                v=validate_review(json.loads(review.read_text()),grade['sha']);row['critical_reviewed_stages']+=1
                row['critical_findings']+=sum(x['value'] for x in v['critical'].values())
        call_lanes={}
        for line in (path/'events.jsonl').read_text().splitlines():
            e=json.loads(line)
            if e['kind']=='call_start':call_lanes[e['call_id']]=e['lane']
            if e['kind']=='call_start' and not e.get('simulated'):row['provider_calls']+=1
            if e['kind']=='call_end' and e.get('usage'):
                lane=call_lanes.get(e.get('call_id'),'unspecified');totals=row['usage_by_lane'].setdefault(lane,{})
                for k,v in e['usage'].items():
                    if type(v) in (int,float) and math.isfinite(v):totals[k]=totals.get(k,0)+v
        row['result_sha256']=digest(r);result.append(row)
    return result


def checkpoint(p,root,count):
    data=rows(p,root)[:count]
    if len(data)!=count or any(not r['observed'] for r in data):raise ValueError('checkpoint requires complete prefix, including both paired arms')
    reasons=[]
    if any(r.get('unclosed_calls') for r in data):reasons.append('unclosed model calls')
    if any(r['new_protected_violations'] or r['critical_findings'] for r in data):reasons.append('observed critical/protected-work failure')
    pooled={}
    for level in ('middle','ultra'):
        selected=[r for r in data if r['difficulty']==level]
        if selected and p['phase']!='routing':pooled[level]=sum(r['final_correct'] for r in selected)/len(selected)
    if p['phase']=='calibration' and count>=6 and not .2<=pooled.get('middle',-1)<=.8:
        reasons.append('middle-band ceiling/floor; revise tasks, do not extend')
    if p['phase']=='calibration' and count>=6:
        middle=[r for r in data if r['difficulty']=='middle']
        means={ident:sum(r['final_correct'] for r in middle if r['project']==ident)/sum(r['project']==ident for r in middle) for ident in {r['project'] for r in middle}}
        if not any(0<v<1 for v in means.values()):reasons.append('no mixed middle project; pooled extremes are not a middle band')
    if p['phase']=='calibration' and count>=6 and not any(r.get('trajectory_correct') for r in data if r['difficulty']=='middle'):
        reasons.append('middle trajectories all fail; partial stages are not a completion band')
    # Upper-edge floor is informative. An ultra ceiling refutes the hardness prediction.
    if p['phase'] in ('calibration','upper-diagnostic') and count==len(p['trials']) and pooled.get('ultra',0)>.85:
        reasons.append('upper-edge ceiling; ultra difficulty prediction not supported')
    return dict(plan_sha256=digest(p),completed=count,results_sha256=digest(data),pooled_stage_pass=pooled,
                mechanical_stop_reasons=reasons,requires_operator_audit=True,arm_comparison='withheld at validity gate')


def approve_checkpoint(c,a):
    if c['mechanical_stop_reasons']:raise ValueError('mandatory stop: '+str(c['mechanical_stop_reasons']))
    if a.get('checkpoint_sha256')!=digest(c) or not a.get('reviewer') or not a.get('evidence'):
        raise ValueError('audit must name a reviewer, inspected evidence and exact checkpoint')
    for k in ('no_personal_memory','no_evaluator_access','no_artifact_failures','no_critical_failures','trace_coverage_sufficient'):
        if a.get(k) is not True:raise ValueError('checkpoint audit incomplete or failed: '+k)
    return digest(a)


def execute(p,out,audit_file,resume=False,calibration=None):
    validate(p); out=Path(out).resolve()
    if out.is_relative_to(ROOT):raise ValueError('all evidence must stay outside the public repository')
    audit=json.loads(Path(audit_file).read_text()); native_hash=native_audit(audit,p)
    if read_native_versions()!=audit['cli_versions']:raise ValueError('installed CLI changed since native preflight')
    if p['phase']=='upper-diagnostic':
        if calibration is None:raise ValueError('upper-only diagnostic must link its stopped primary calibration')
        calroot=Path(calibration);cal=json.loads((calroot/'plan.json').read_text());validate(cal)
        if cal['phase']!='calibration':raise ValueError('not a primary calibration')
        c=checkpoint(cal,calroot,6)
        allowed={'middle-band ceiling/floor; revise tasks, do not extend','no mixed middle project; pooled extremes are not a middle band','middle trajectories all fail; partial stages are not a completion band'}
        if not c['mechanical_stop_reasons'] or not set(c['mechanical_stop_reasons']).issubset(allowed):raise ValueError('not a clean discrimination-only stop')
        if any((calroot/t['id']).exists() for t in cal['trials'] if t['difficulty']=='ultra'):raise ValueError('upper work already attempted; do not selectively duplicate it')
        authorization=json.loads((calroot/'upper-only-authorization.json').read_text())
        if authorization.get('checkpoint_sha256')!=digest(c) or authorization.get('scope')!='upper-only diagnostic; no extension' or not authorization.get('reviewer') or not authorization.get('evidence'):raise ValueError('explicit scoped diagnostic authorization required')
        for key in ('no_personal_memory','no_evaluator_access','no_artifact_failures','no_critical_failures','trace_coverage_sufficient'):
            if authorization.get(key) is not True:raise ValueError('diagnostic validity unresolved: '+key)
    if p['phase']=='extension':
        if calibration is None:raise ValueError('extension requires accepted calibration directory')
        calroot=Path(calibration); cal=json.loads((calroot/'plan.json').read_text());validate(cal)
        if cal['phase']!='calibration':raise ValueError('only primary calibration can authorize extension')
        c=checkpoint(cal,calroot,len(cal['trials']))
        approve_checkpoint(c,json.loads((calroot/f'audit-{len(cal["trials"])}.json').read_text()))
    if out.exists() and not resume:raise FileExistsError('explicit resume required')
    out.mkdir(parents=True,exist_ok=True)
    import fcntl
    with (out/'round.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (out/'plan.json').exists() and json.loads((out/'plan.json').read_text())!=p:raise ValueError('another plan owns this output')
        atomic(out/'plan.json',p)
        clock=json.loads((out/'clock.json').read_text()) if (out/'clock.json').exists() else {}
        remaining=deadline(clock,p['wall_cap_s']);atomic(out/'clock.json',clock)
        if not remaining:return 'STOP_WALL_CAP'
        event(out/'dispatch.jsonl','round_attempt',native_audit_sha256=native_hash)
        for i,trial in enumerate(p['trials']):
            if i in p['checkpoints']:
                c=checkpoint(p,out,i);atomic(out/f'checkpoint-{i}.json',c)
                if c['mechanical_stop_reasons']:return 'STOP_INVALID'
                audit_path=out/f'audit-{i}.json'
                if not audit_path.exists():return 'PAUSED_VALIDITY'
                approve_checkpoint(c,json.loads(audit_path.read_text()))
            directory=out/trial['id']
            if (directory/'result.json').exists():continue
            remaining=deadline(clock,p['wall_cap_s'])
            if remaining<1:return 'STOP_WALL_CAP'
            command=[sys.executable,str(Path(__file__).resolve()),'trial','--plan',str(out/'plan.json'),'--id',trial['id'],'--out',str(directory)]
            if directory.exists():command.append('--resume')
            event(out/'dispatch.jsonl','dispatch_start',trial=trial['id'])
            with (out/(trial['id']+'.log')).open('ab') as log:
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                try:code=child.wait(timeout=min(remaining,trial['timeout_s']+15))
                except BaseException:
                    try:os.killpg(child.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    child.wait();event(out/'dispatch.jsonl','dispatch_interrupted',trial=trial['id']);raise
            event(out/'dispatch.jsonl','dispatch_end',trial=trial['id'],returncode=code)
            if code:return 'STOP_INTERRUPTED'
            # Validate receipts after every trajectory; never silently repeat or discard.
            latest=rows(p,out)[i]
            if latest['new_protected_violations'] or latest['critical_findings'] or latest.get('unclosed_calls'):return 'STOP_CRITICAL_OR_UNCLOSED'
        c=checkpoint(p,out,len(p['trials']));atomic(out/f'checkpoint-{len(p["trials"])}.json',c)
        return 'STOP_INVALID' if c['mechanical_stop_reasons'] else 'PAUSED_FINAL_AUDIT'


def main():
    ap=argparse.ArgumentParser(description=__doc__); sub=ap.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('native-template');q.add_argument('--out',type=Path,required=True)
    q=sub.add_parser('plan');q.add_argument('--name',required=True);q.add_argument('--phase',choices=PHASES,default='calibration');q.add_argument('--seed',type=int,default=261001);q.add_argument('--out',type=Path,required=True)
    q=sub.add_parser('execute');q.add_argument('--plan',type=Path,required=True);q.add_argument('--out',type=Path,required=True);q.add_argument('--native-audit',type=Path,required=True);q.add_argument('--resume',action='store_true');q.add_argument('--calibration',type=Path)
    q=sub.add_parser('trial');q.add_argument('--plan',type=Path,required=True);q.add_argument('--id',required=True);q.add_argument('--out',type=Path,required=True);q.add_argument('--resume',action='store_true')
    q=sub.add_parser('report');q.add_argument('--plan',type=Path,required=True);q.add_argument('--runs',type=Path,required=True);q.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    if a.cmd=='native-template':
        if a.out.exists():raise FileExistsError('do not overwrite an audit')
        atomic(a.out,dict(source_fingerprint=fingerprint(ROOT),reviewer='',evidence=[],cli_versions=read_native_versions(),
            memory_injection_absent=None,subscription_auth_unchanged=None,node_available=None,cgroup_limits_verified=None))
    elif a.cmd=='plan':
        if a.out.exists():raise FileExistsError('do not overwrite a frozen plan')
        p=plan(a.name,a.phase,a.seed);atomic(a.out,p);print(json.dumps({'trajectories':len(p['trials']),'maximum_stages':p['maximum_stage_runs'],'wall_cap_s':p['wall_cap_s']}))
    else:
        p=json.loads(a.plan.read_text());validate(p)
        if a.cmd=='execute':print(execute(p,a.out,a.native_audit,a.resume,a.calibration))
        elif a.cmd=='report':atomic(a.out,{'rows':rows(p,a.runs),'promotion':False,'uncertainty':'Calibration is diagnostic; six synthetic projects include one previously exposed bridge. Missing outcomes and unreviewed critical categories remain unknown.'})
        else:
            if not memory_implementation_available():raise ValueError('memory implementation missing; stop before worker dispatch')
            matches=[t for t in p['trials'] if t['id']==a.id]
            if len(matches)!=1:raise ValueError('unknown or duplicate trial ID')
            t=matches[0];project=next(x for x in catalog() if x['id']==t['project'])
            r=run_project(project,a.out,t['policy'],p['mode'],resume=a.resume,timeout=t['timeout_s'],
                comparison_tier=p['comparison_tier'],isolate_memories=True,offline_handoff=True,defer_grading=True,routing_only=p['phase']=='routing')
            if r.get('incomplete'):raise SystemExit(2)

if __name__=='__main__':main()
