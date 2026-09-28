"""Run a durable two-stage synthetic project through the existing aa coordinator.

Evaluator-only hidden checks run after worker work has stopped, in detached
worktrees. The first submitted implementation and final delivery are separate.
Interruptions here are recorded step-boundary simulations, not power-loss tests.
"""
from __future__ import annotations
import fcntl, json, os, subprocess, sys, threading, time, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from aa import config
from aa.db import DB
from aa.daemon import App
from aa.workers import Workers, Result
from tools.ho01_records import fingerprint
from tools.ho01_round import POLICIES
from tools.ho02_projects import write_tree
from tools.ho02_support import atomic, bounded, digest, event, pending_calls, rubric
from tools.ho03_support import deadline, handoff, owner_resolution, preservation, protected_hashes

TERMINAL={'DONE','FAILED','BLOCKED','CANCELLED','DEEP','AWAITING_PRO','ROUTED_LOCAL'}


def git(root,*args):
    return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True,text=True).stdout.strip()


def snapshot_grade(repo, sha, hidden, target, protected, stage_start=None):
    if sha is None: return None
    target.mkdir(parents=True,exist_ok=False)
    check=target/'checkout'
    git(repo,'worktree','add','-q','--detach',str(check),sha)
    try:
        preserved=preservation(check,protected,stage_start)
        write_tree(check,hidden)
        hidden_result=bounded([sys.executable,'-m','unittest','discover','-s','tests','-t','.', '-p','test_hidden_*.py'],check)
        all_result=bounded([sys.executable,'-m','unittest','discover','-s','tests','-t','.'],check)
        atomic(target/'hidden.json',hidden_result); atomic(target/'combined.json',all_result)
        return {'sha':sha,'hidden_pass':hidden_result['passed'],'all_tests_pass':all_result['passed'],
                **preserved,'rubric':rubric(sha)}
    finally: git(repo,'worktree','remove','--force',str(check))


def effective_config(policy, state, *, isolate_memories=False):
    overrides={'paths':{'state_dir':str(state)},'ntfy':{'enabled':False},'delivery':{'push_branch':False}}
    for section,values in POLICIES[policy].items(): overrides.setdefault(section,{}).update(values)
    if isolate_memories:
        overrides.setdefault('harness_opt',{}).update(codex_no_memories=True,gate_shadow=True)
        overrides.setdefault('triage',{})['policy']='codex'
    return config.load(overrides=overrides)


def config_hash(cfg):
    return digest({k:v for k,v in cfg.data.items() if k!='paths'})


def run_project(project, dest, policy, mode='routed', *, resume=False, timeout=1800, worker_factory=None,
                comparison_tier=None, isolate_memories=False, offline_handoff=False, defer_grading=False, routing_only=False):
    if routing_only and mode!='routed':raise ValueError('routing-only is a separate routed diagnostic')
    if comparison_tier not in (None,'medium_tough') or (comparison_tier and mode!='bounded'):
        raise ValueError('strong comparison is bounded-only')
    dest=Path(dest).resolve()
    if dest.is_relative_to(ROOT): raise ValueError('private run evidence must be outside the public repository')
    if policy not in POLICIES or mode not in ('routed','bounded'): raise ValueError('unknown policy/mode')
    if dest.exists() and not resume: raise FileExistsError('use a new run or explicit resume')
    dest.mkdir(parents=True,exist_ok=True)
    with (dest/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        cfg=effective_config(policy,dest/'state',isolate_memories=isolate_memories)
        identity={'schema_version':2,'effective_config_sha256':config_hash(cfg),'project_hash':digest(project),'source_fingerprint':fingerprint(ROOT),
                  'policy':policy,'flags':POLICIES[policy],'mode':mode,
                  'comparison_tier':comparison_tier,'offline_handoff':offline_handoff,'timeout_s':timeout,
                  'defer_grading':defer_grading,'routing_only':routing_only}
        manifest=dest/'manifest.json'; progress_file=dest/'progress.json'; journal=dest/'events.jsonl'
        if manifest.exists() and json.loads(manifest.read_text())!=identity: raise ValueError('changed source, project, effective configuration, flags or mode')
        if not manifest.exists(): atomic(manifest,identity)
        if (dest/'result.json').exists(): return json.loads((dest/'result.json').read_text())
        progress=json.loads(progress_file.read_text()) if progress_file.exists() else {'stage':0,'completed':[],'fault_used':False,'restarted':False,'first':None,'tid':None}
        remaining=deadline(progress,timeout)
        atomic(progress_file,progress)
        if not remaining:
            event(journal,'deadline',resumed=resume)
            return {'incomplete':True,'resume_required':False,'deadline_exhausted':True,'project':project['id']}
        event(journal,'attempt_start',attempt=uuid.uuid4().hex,unclosed_prior_calls=pending_calls(journal),resumed=resume)
        repo=dest/'repo'
        if not repo.exists():
            write_tree(repo,project['repo'])
            (repo/'.agenticarch.toml').write_text('[checks]\ntests = "python3 -m unittest discover -s tests -t . -q"\n')
            git(repo,'init','-q','-b','main'); git(repo,'config','user.name','project-lab');git(repo,'config','user.email','lab@invalid')
            git(repo,'add','-A'); git(repo,'commit','-qm','synthetic existing project')
        db=DB(dest/'state/aa.sqlite')
        answer_count=0; fault_lock=threading.Lock()
        def make_app():
            workers=worker_factory(cfg) if worker_factory else Workers(cfg)
            original=workers.execute
            def execute(lane,prompt,cwd,**kw):
                remaining=deadline(progress,timeout)
                if not remaining: return Result(False,'',error='trajectory deadline exhausted')
                workers.timeout=min(workers.timeout,max(1,int(remaining))) if hasattr(workers,'timeout') else max(1,int(remaining))
                call_id=uuid.uuid4().hex
                is_work=kw.get('log_name')==progress.get('tid') or '-race-' in kw.get('log_name','')
                with fault_lock:
                    simulated=bool(is_work and project['scenario'].get('fail_first_work') and not progress['fault_used'])
                    if simulated:
                        progress['fault_used']=True; atomic(progress_file,progress)
                event(journal,'call_start',call_id=call_id,lane=lane.name,job=kw.get('log_name'),simulated=simulated)
                start=time.monotonic()
                if simulated:
                    result=Result(False,'',None,[],error='simulated one-time transport interruption')
                else:
                    try: result=original(lane,prompt,cwd,**kw)
                    except Exception as exc:
                        event(journal,'call_end',call_id=call_id,ok=False,usage=None,error=type(exc).__name__,seconds=time.monotonic()-start)
                        raise
                event(journal,'call_end',call_id=call_id,ok=result.ok,usage=result.usage,simulated=simulated,seconds=time.monotonic()-start)
                return result
            workers.execute=execute
            app=App(cfg,db,workers=workers)
            if offline_handoff or comparison_tier:
                def local_escalation(task,reason):
                    number=progress['stage']+1
                    package=handoff(Path(task.get('worktree') or repo),task,dest/f'handoff-stage-{number}')
                    task['data']['offline_handoff']=package
                    db.update_task(task['id'],status='AWAITING_PRO',data=task['data'],result='Awaiting Pro: '+reason)
                    event(journal,'offline_handoff',stage=number,reason=reason,complete=package['mechanically_complete'])
                app.tasks._to_deep=local_escalation
            app.n.send=lambda title,msg,**kw:event(journal,'notification',title=title,choices=bool(kw.get('choices')))
            app.recover()
            return app
        app=make_app(); started=time.monotonic()
        try:
            while progress['stage']<len(project['stages']):
                stage=project['stages'][progress['stage']]; number=progress['stage']+1
                if not progress['tid']:
                    # A crash after create_task but before progress.json must not duplicate a dispatch.
                    prior=db.q('SELECT id FROM tasks WHERE prompt=?',(stage['prompt'],))
                    if len(prior)>1: raise ValueError('ambiguous stage identity')
                    progress['tid']=prior[0]['id'] if prior else app.tasks.create(repo,stage['prompt'],None if mode=='routed' else (comparison_tier or 'bounded'))
                    atomic(progress_file,progress)
                if 'protected_start' not in progress:
                    progress['protected_start']=protected_hashes(repo,project['protected']); atomic(progress_file,progress)
                tid=progress['tid']; answered=None
                while True:
                    task=db.task(tid)
                    if task['status'] in TERMINAL: break
                    if not deadline(progress,timeout):
                        event(journal,'deadline',stage=number); return {'incomplete':True,'resume_required':False,'deadline_exhausted':True,'project':project['id']}
                    if task['status']=='TRIAGED' and routing_only and task['tier']!='tough':
                        db.update_task(tid,status='ROUTED_LOCAL',result='Routing-only diagnostic: implementation not attempted.')
                        event(journal,'routing_only_local',tier=task['tier']);break
                    if task['status']=='TRIAGED' and comparison_tier:
                        data=task['data']; tri=data.setdefault('triage',{})
                        data.setdefault('lab_original_triage',dict(tri));tri['peer']='astra'
                        db.update_task(tid,data=data)
                    if task['status']=='VERIFY' and progress['first'] is None:
                        progress['first']=git(Path(task['worktree']),'rev-parse','HEAD'); atomic(progress_file,progress)
                        event(journal,'first_submission',stage=number,sha=progress['first'])
                        if project['scenario'].get('restart_after_first') and not progress['restarted']:
                            progress['restarted']=True; atomic(progress_file,progress)
                            event(journal,'simulated_restart',stage=number)
                            db.conn.close(); db=DB(dest/'state/aa.sqlite'); app=make_app(); continue
                    if task['status']=='WAIT_OWNER':
                        if answered==task['updated']: raise ValueError('owner reply did not advance')
                        answered=task['updated']; data=task['data']; q=str(data.get('worker_question') or '')
                        if data.get('spec_wait') or data.get('env_wait'):
                            event(journal,'handback',stage=number,reason='no simulated authority to waive failed checks')
                            break
                        if q:
                            facts=stage.get('owner_facts',{})
                            answer=next((value for key,value in facts.items() if key.casefold() in q.casefold()),
                                'No additional fact is available. Preserve the documented constraints and state uncertainty.')
                            app.handle_reply(f'answer {tid} {answer}'); answer_count+=1
                            event(journal,'owner_answer',stage=number,question=q,answer=answer)
                        else:
                            action,value=owner_resolution(task,db.repo_checks(task['repo']))
                            if action=='handback':
                                event(journal,'handback',stage=number,reason=value);break
                            app.handle_reply(f'{action} {tid} {value}')
                            event(journal,'simulated_'+action+'_resolution',stage=number)
                        continue
                    app.tick()
                task=db.task(tid)
                final=git(repo,'rev-parse',task['branch']) if task['status']=='DONE' else None
                # Grading is after all model work for this stage. Its output never becomes retry feedback.
                grade_dir=dest/f'grade-stage-{number}-attempt-{uuid.uuid4().hex}'
                protected={p:project['repo'][p] for p in project['protected']}
                before=progress['protected_start']
                first=None if defer_grading else snapshot_grade(repo,progress['first'],stage['hidden_tests'],grade_dir/'first',protected,before)
                last=None if defer_grading else snapshot_grade(repo,final,stage['hidden_tests'],grade_dir/'final',protected,before)
                record={'stage':number,'status':task['status'],'first':first,'final':last,
                        'first_sha':progress['first'],'final_sha':final,'protected_start':before,
                        'correct_delivery':None if defer_grading else bool(last and last['hidden_pass'] and last['all_tests_pass'] and last['protected_preserved']),
                        'task':{k:v for k,v in task.items() if k!='repo'},'grade_directory':str(grade_dir),
                        'handoff':task['data'].get('offline_handoff')}
                atomic(dest/f'stage-{number}.json',record)
                progress['completed'].append(record); progress['stage']+=1;progress['tid']=None;progress['first']=None;progress.pop('protected_start',None)
                if final: git(repo,'checkout','-q','--detach',final)
                atomic(progress_file,progress)
                if task['status']!='DONE': break
            if defer_grading:
                # No stage-one hidden output exists during stage-two model work.
                event(journal,'model_trajectory_ended')
                for record in progress['completed']:
                    number=record['stage']; stage=project['stages'][number-1]
                    grade_dir=Path(record['grade_directory'])
                    originals={p:project['repo'][p] for p in project['protected']}
                    for key in ('first','final'):
                        if record[key] is None and record.get(key+'_sha'):
                            target=grade_dir/key
                            if target.exists():
                                # Interrupted grading leaves inspectable evidence; do not
                                # overwrite it or pretend it was a previous successful grade.
                                target=grade_dir/(key+'-retry-'+uuid.uuid4().hex)
                            record[key]=snapshot_grade(repo,record[key+'_sha'],stage['hidden_tests'],target,originals,record['protected_start'])
                    last=record['final']
                    record['correct_delivery']=bool(record['status']=='DONE' and last and last['hidden_pass'] and last['all_tests_pass'] and last['protected_preserved'])
                    record['stage_delta_correct']=bool(record['status']=='DONE' and last and last['hidden_pass'] and last['all_tests_pass'] and not last['protected_changed_this_stage'])
                    atomic(dest/f'stage-{number}.json',record);atomic(progress_file,progress)
            result={'schema_version':1,'project':project['id'],'family':project['family'],'weight':project['weight'],
                'scope':project['scope'],'policy':policy,'mode':mode,'stages':progress['completed'],
                'all_stages_attempted':len(progress['completed'])==len(project['stages']),
                'unclosed_calls':pending_calls(journal),'critical_unreviewed':True,
                'owner_questions_this_attempt':answer_count,'attempt_seconds':time.monotonic()-started,
                'elapsed_since_first_start':time.time()-progress['started_at'],'deadline_at':progress['deadline_at']}
            atomic(dest/'result.json',result); event(journal,'attempt_end',complete=True)
            return result
        finally: db.conn.close()
