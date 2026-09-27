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

TERMINAL={'DONE','FAILED','BLOCKED','CANCELLED','DEEP'}


def git(root,*args):
    return subprocess.run(['git',*args],cwd=root,check=True,capture_output=True,text=True).stdout.strip()


def snapshot_grade(repo, sha, hidden, target, protected):
    if sha is None: return None
    target.mkdir(parents=True,exist_ok=False)
    check=target/'checkout'
    git(repo,'worktree','add','-q','--detach',str(check),sha)
    try:
        preserved=all((check/name).is_file() and not (check/name).is_symlink() and
                      (check/name).read_text()==text for name,text in protected.items())
        write_tree(check,hidden)
        hidden_result=bounded([sys.executable,'-m','unittest','discover','-s','tests','-t','.', '-p','test_hidden_*.py'],check)
        all_result=bounded([sys.executable,'-m','unittest','discover','-s','tests','-t','.'],check)
        atomic(target/'hidden.json',hidden_result); atomic(target/'combined.json',all_result)
        return {'sha':sha,'hidden_pass':hidden_result['passed'],'all_tests_pass':all_result['passed'],
                'protected_preserved':preserved,'rubric':rubric(sha)}
    finally: git(repo,'worktree','remove','--force',str(check))


def effective_config(policy, state):
    overrides={'paths':{'state_dir':str(state)},'ntfy':{'enabled':False},'delivery':{'push_branch':False}}
    for section,values in POLICIES[policy].items(): overrides.setdefault(section,{}).update(values)
    return config.load(overrides=overrides)


def config_hash(cfg):
    return digest({k:v for k,v in cfg.data.items() if k!='paths'})


def run_project(project, dest, policy, mode='routed', *, resume=False, timeout=1800, worker_factory=None):
    dest=Path(dest).resolve()
    if dest.is_relative_to(ROOT): raise ValueError('private run evidence must be outside the public repository')
    if policy not in POLICIES or mode not in ('routed','bounded'): raise ValueError('unknown policy/mode')
    if dest.exists() and not resume: raise FileExistsError('use a new run or explicit resume')
    dest.mkdir(parents=True,exist_ok=True)
    with (dest/'lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        cfg=effective_config(policy,dest/'state')
        identity={'schema_version':2,'effective_config_sha256':config_hash(cfg),'project_hash':digest(project),'source_fingerprint':fingerprint(ROOT),
                  'policy':policy,'flags':POLICIES[policy],'mode':mode}
        manifest=dest/'manifest.json'; progress_file=dest/'progress.json'; journal=dest/'events.jsonl'
        if manifest.exists() and json.loads(manifest.read_text())!=identity: raise ValueError('changed source, project, effective configuration, flags or mode')
        if not manifest.exists(): atomic(manifest,identity)
        if (dest/'result.json').exists(): return json.loads((dest/'result.json').read_text())
        progress=json.loads(progress_file.read_text()) if progress_file.exists() else {'stage':0,'completed':[],'fault_used':False,'restarted':False,'first':None,'tid':None}
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
                    progress['tid']=prior[0]['id'] if prior else app.tasks.create(repo,stage['prompt'],None if mode=='routed' else 'bounded')
                    atomic(progress_file,progress)
                tid=progress['tid']; answered=None
                while True:
                    task=db.task(tid)
                    if task['status'] in TERMINAL: break
                    if time.monotonic()-started>timeout:
                        event(journal,'deadline',stage=number); return {'incomplete':True,'resume_required':True,'project':project['id']}
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
                        elif (data.get('tier_votes') or {}).get('codex'):
                            app.handle_reply(f'tier {tid} {data["tier_votes"]["codex"]}')
                            event(journal,'simulated_tier_resolution',stage=number)
                        else: app.handle_reply(f'checks {tid} ok')
                        continue
                    app.tick()
                task=db.task(tid)
                final=git(repo,'rev-parse',task['branch']) if task['status']=='DONE' else None
                # Grading is after all model work for this stage. Its output never becomes retry feedback.
                grade_dir=dest/f'grade-stage-{number}-attempt-{uuid.uuid4().hex}'
                protected={p:project['repo'][p] for p in project['protected']}
                first=snapshot_grade(repo,progress['first'],stage['hidden_tests'],grade_dir/'first',protected)
                last=snapshot_grade(repo,final,stage['hidden_tests'],grade_dir/'final',protected)
                record={'stage':number,'status':task['status'],'first':first,'final':last,
                        'correct_delivery':bool(last and last['hidden_pass'] and last['all_tests_pass'] and last['protected_preserved']),
                        'task':{k:v for k,v in task.items() if k!='repo'},'grade_directory':str(grade_dir)}
                atomic(dest/f'stage-{number}.json',record)
                progress['completed'].append(record); progress['stage']+=1;progress['tid']=None;progress['first']=None
                if final: git(repo,'checkout','-q','--detach',final)
                atomic(progress_file,progress)
                if task['status']!='DONE': break
            result={'schema_version':1,'project':project['id'],'family':project['family'],'weight':project['weight'],
                'scope':project['scope'],'policy':policy,'mode':mode,'stages':progress['completed'],
                'all_stages_attempted':len(progress['completed'])==len(project['stages']),
                'unclosed_calls':pending_calls(journal),'critical_unreviewed':True,
                'owner_questions_this_attempt':answer_count,'attempt_seconds':time.monotonic()-started}
            atomic(dest/'result.json',result); event(journal,'attempt_end',complete=True)
            return result
        finally: db.conn.close()
