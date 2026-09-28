"""Runtime regression entry point; unchanged pre-HO02 cases live in runtime_legacy.

The legacy module is deliberately not a test_*.py file, so discovery runs each
case once. New behavioural tests remain here at the documented entry point.
"""
if __package__:
    from .runtime_legacy import *  # noqa: F403
else:
    from runtime_legacy import *  # noqa: F403


class HO02ReviewTests(unittest.TestCase):
    def test_assertion_list_diff_and_suffix_are_not_discarded(self):
        from aa.context import focused_failure
        suffix = 'noise\n' * 800 + 'FAIL: test_values\nAssertionError: lists differ\n'
        suffix += '- [1, 2, 3]\n+ [1, 9, 3]\n' + 'details\n' * 15 + 'FAILED (failures=1)\n'
        text = 'prefix\n' * 500 + suffix
        result = focused_failure(text, 6000)
        self.assertEqual(result, text[-6000:])
        self.assertIn('+ [1, 9, 3]', focused_failure(result, 3000))

    def test_more_than_twelve_diagnostics_fit_and_unused_room_is_spent(self):
        from aa.context import focused_failure
        text = ''.join(f'noise {i}\n' * 25 + f'AssertionError: case-{i:02d}\n'
                       + f'- expected-{i}\n+ actual-{i}\n' for i in range(20)) + 'tail\n' * 50
        result = focused_failure(text, 5000)
        self.assertLessEqual(len(result), 5000)
        self.assertGreater(len(result), 4800)
        for i in range(20):
            self.assertIn(f'case-{i:02d}', result)
            self.assertIn(f'+ actual-{i}', result)

    def test_context_hard_cap_with_large_lines_and_tiny_budgets(self):
        from aa.context import focused_failure
        import random
        rng = random.Random(260927)
        for _ in range(250):
            text = ''.join(rng.choice(['noise', 'AssertionError:', '\n', 'x' * 100]) for _ in range(200))
            limit = rng.randrange(0, 2000)
            self.assertLessEqual(len(focused_failure(text, limit)), limit)


class HO02StopTests(unittest.TestCase):
    setUp = HarnessOptStopTests.setUp
    install = HarnessOptStopTests.install
    invoke = HarnessOptStopTests.invoke
    def test_subdirectory_runs_frozen_root_checks_but_symlink_escape_does_not(self):
        sub = self.wt / 'package'; sub.mkdir()
        settings = self.install({'test': 'test -f fixed'})
        reply, _ = self.invoke(settings, {'hook_event_name': 'Stop', 'cwd': str(sub)})
        self.assertEqual(reply['decision'], 'block')
        (self.wt / 'fixed').touch()
        self.assertEqual(self.invoke(settings, {'hook_event_name': 'Stop', 'cwd': str(sub)})[0], {})
        (self.wt / 'escape').symlink_to(self.root, target_is_directory=True)
        self.assertEqual(self.invoke(settings, {'hook_event_name': 'Stop', 'cwd': str(self.wt / 'escape')})[0], {})

    def test_capsule_and_project_settings_use_absolute_denies(self):
        settings = self.install()
        _, policy = self.invoke(settings)
        for path in (policy.parent, self.wt / '.claude'):
            self.assertNotIn(f'Write(/{path.as_posix()}/**)', settings['permissions']['deny'])
            self.assertIn(f'Edit(/{path.as_posix()}/**)', settings['permissions']['deny'])
        self.assertIs(settings['disableAllHooks'], False)

    def test_modified_hook_code_is_not_executed(self):
        settings = self.install()
        _, policy = self.invoke(settings)
        (policy.parent / 'hook.py').write_text("raise RuntimeError('foreign executable ran')")
        self.assertEqual(self.invoke(settings)[0], {})


class HO02ProjectTests(unittest.TestCase):
    def test_all_twelve_stages_validate_with_original_importer(self):
        from tools.ho02_projects import catalog, validate_projects
        ps=catalog()
        self.assertAlmostEqual(sum(p['weight'] for p in ps),1)
        self.assertEqual(len(ps),6)
        results=validate_projects(ps)
        self.assertEqual(len(results),12)
        self.assertTrue(all(r['valid'] for r in results),results)

    def test_plan_is_paired_and_tampering_fails(self):
        from tools.ho02_round import plan, validate
        p=plan('test-plan',2); self.assertEqual(p['maximum_task_runs'],48)
        validate(p)
        from collections import Counter
        groups=Counter((t['project'],t['repeat']) for t in p['trials'])
        self.assertEqual(set(groups.values()),{2})
        p['trials'][0]['policy']='stop'
        with self.assertRaises(ValueError):validate(p)

    def test_unknown_rubric_is_not_a_pass_and_stale_review_fails(self):
        from tools.ho02_support import rubric,validate_review
        r=rubric('abc');self.assertTrue(all(v is None for v in r['critical'].values()))
        with self.assertRaises(ValueError):validate_review(r,'abc')
        r['reviewer']='independent-test-reviewer'
        for section in ('dimensions','critical'):
            r[section]={k:{'value':False if section=='critical' else 3,'evidence':'inspected artifact x'} for k in r[section]}
        validate_review(r,'abc')
        with self.assertRaises(ValueError):validate_review(r,'different')

    def test_first_final_restart_and_followup_use_actual_prior_result(self):
        from tools.ho02_project_run import run_project
        from tools.ho02_projects import catalog, write_tree
        p=catalog()[0]; state={'writes':0,'stage2_saw_first':False}
        def factory(cfg):
            def work(lane,cwd,prompt,extra):
                self.assertFalse((cwd/'hidden-1').exists())
                self.assertNotIn('test_hidden_project',prompt)
                if 'customer now' in prompt:
                    state['stage2_saw_first']='csv.writer' in (cwd/'formats.py').read_text()
                    write_tree(cwd,p['stages'][1]['reference'])
                else:
                    state['writes']+=1
                    # First candidate is intentionally wrong, then a visible
                    # assertion requests repair. No hidden result is fed back.
                    if state['writes']==1:
                        (cwd/'tests/test_visible_repair.py').write_text('import unittest\nfrom service import export\nclass T(unittest.TestCase):\n def test_csv(self): self.assertIn("id,value",export([],"csv"))\n')
                    else: write_tree(cwd,p['stages'][0]['reference'])
                return Result(True,'',{'status':'done','summary':'scripted fixture producer','open_items':[],'question':'','rebuttals':[],'spec_conflicts':[]},[lane.model])
            return FakeWorkers(cfg,{'triage':triage('bounded',testable=False),'work':work})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trial'
            r=run_project(p,path,'minimal',worker_factory=factory)
            self.assertFalse(r['stages'][0]['first']['hidden_pass'])
            self.assertTrue(r['stages'][0]['final']['hidden_pass'])
            self.assertTrue(r['stages'][1]['correct_delivery'])
            self.assertTrue(state['stage2_saw_first'])
            self.assertIn('simulated_restart',(path/'events.jsonl').read_text())
            calls=state['writes']; again=run_project(p,path,'minimal',resume=True,worker_factory=factory)
            self.assertEqual(calls,state['writes']); self.assertEqual(r,again)
            p['stages'][0]['prompt']+=' changed'
            with self.assertRaises(ValueError):run_project(p,path,'minimal',resume=True,worker_factory=factory)

    def test_injected_failure_is_once_and_journalled(self):
        from tools.ho02_project_run import run_project
        from tools.ho02_projects import catalog,write_tree
        p=catalog()[0];p['scenario']={'fail_first_work':True};p['stages']=p['stages'][:1]
        def factory(cfg):
            def work(lane,cwd,prompt,extra):
                write_tree(cwd,p['stages'][0]['reference'])
                return Result(True,'',{'status':'done','summary':'fixture','open_items':[],'question':''},[lane.model])
            return FakeWorkers(cfg,{'triage':triage('bounded',testable=False),'work':work})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'trial'; r=run_project(p,path,'minimal',worker_factory=factory)
            self.assertTrue(r['stages'][0]['correct_delivery'])
            events=[json.loads(l) for l in (path/'events.jsonl').read_text().splitlines()]
            self.assertEqual(sum(e['kind']=='call_start' and e.get('simulated',False) for e in events),1)
            self.assertEqual(r['unclosed_calls'],[])

    def test_grader_timeout_and_unclosed_call_evidence(self):
        from tools.ho02_support import bounded,event,pending_calls
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp); r=bounded([sys.executable,'-c','import time;time.sleep(60)'],path,.1)
            self.assertFalse(r['passed']);self.assertTrue(r['timeout'])
            log=path/'events';event(log,'call_start',call_id='one');self.assertEqual(pending_calls(log),['one'])
            event(log,'call_end',call_id='one');self.assertEqual(pending_calls(log),[])

class HO02ProjectGuardTests(unittest.TestCase):
    def test_missing_trials_are_bounds_not_zero_or_perfect_success(self):
        from tools.ho02_round import plan
        from tools.ho02_report import report
        with tempfile.TemporaryDirectory() as tmp:
            r=report(plan('missing',1),Path(tmp))
            self.assertEqual(r['arms']['full']['final_bounds'],[0,1])
            self.assertFalse(r['all_reviews_complete']);self.assertFalse(r['promotion'])
    def test_declared_owner_fact_reaches_subsequent_triage(self):
        from tools.ho02_projects import catalog,write_tree
        from tools.ho02_project_run import run_project
        p=catalog()[4];p['stages']=p['stages'][:1];seen=[]
        class W(FakeWorkers):
            def execute(s,lane,prompt,cwd,**kw):
                if kw.get('log_name','').endswith('-triage'):
                    seen.append(prompt)
                    answer='Use the latency profile' in prompt
                    return Result(True,'',dict(triage('bounded'),owner_question='' if answer else 'Which profile?'),[lane.model])
                return super().execute(lane,prompt,cwd,**kw)
        def factory(cfg):
            def work(lane,cwd,prompt,extra):
                write_tree(cwd,p['stages'][0]['reference']);return Result(True,'done',None,[lane.model])
            return W(cfg,{'work':work})
        with tempfile.TemporaryDirectory() as tmp:
            result=run_project(p,Path(tmp)/'trial','minimal',worker_factory=factory)
            self.assertEqual(result['owner_questions_this_attempt'],1)
            self.assertTrue(result['stages'][0]['correct_delivery'])
            self.assertIn('Use the latency profile',seen[-1])
    def test_grader_reaps_ordinary_descendants_and_caps_output(self):
        from tools.ho02_support import bounded
        import time
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            child="import time,pathlib;time.sleep(.5);pathlib.Path('escaped').touch()"
            parent=f"import subprocess,sys,time;subprocess.Popen([sys.executable,'-c',{child!r}]);time.sleep(30)"
            r=bounded([sys.executable,'-c',parent],p,.1);time.sleep(.6)
            self.assertTrue(r['timeout']);self.assertFalse((p/'escaped').exists())
            r=bounded([sys.executable,'-c',"print('x'*200000)"],p,3)
            self.assertTrue(r['passed']);self.assertTrue(r['output_truncated']);self.assertLessEqual(len(r['output']),65536)

    def test_review_dimensions_and_critical_types_remain_separate(self):
        from tools.ho02_round import plan
        from tools.ho02_report import report
        from tools.ho02_support import atomic,rubric
        p=plan('rubrics',1);t=p['trials'][0]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/t['id'];path.mkdir()
            stages=[]
            for i in (1,2):
                grade={'sha':str(i),'hidden_pass':True,'all_tests_pass':True,'protected_preserved':True}
                stages.append({'stage':i,'status':'DONE','first':grade,'final':grade,'correct_delivery':True})
                r=rubric(str(i));r['reviewer']='fixture-reviewer'
                r['dimensions']={k:{'value':2 if k=='handoff' else 3,'evidence':'inspected fixture'} for k in r['dimensions']}
                r['critical']={k:{'value':k=='fabricated_verification' and i==2,'evidence':'inspected fixture'} for k in r['critical']}
                atomic(path/f'review-stage-{i}.json',r)
            atomic(path/'result.json',dict(project=t['project'],policy=t['policy'],stages=stages))
            from tools.ho02_projects import catalog
            from tools.ho02_support import digest
            from tools.ho01_round import POLICIES
            project=next(x for x in catalog() if x['id']==t['project'])
            atomic(path/'manifest.json',dict(source_fingerprint=p['source_fingerprint'],mode=p['mode'],
                policy=t['policy'],flags=POLICIES[t['policy']],project_hash=digest(project),
                effective_config_sha256=p['effective_config_hashes'][t['policy']]))
            row=report(p,root)['rows'][0]
            self.assertEqual(row['dimensions']['handoff'],2)
            self.assertEqual(row['critical_by_type']['fabricated_verification'],1)
            self.assertTrue(row['review_coverage'])
            self.assertEqual(row['final'],1)


class HO02ReceiptIntegrityTests(unittest.TestCase):
    def fixture(self,root):
        from tools.ho02_round import plan
        from tools.ho02_projects import catalog
        from tools.ho02_support import atomic,digest
        from tools.ho01_round import POLICIES
        p=plan('receipt-check',1); t=p['trials'][0]; path=root/t['id'];path.mkdir()
        project=next(x for x in catalog() if x['id']==t['project'])
        atomic(path/'manifest.json',dict(source_fingerprint=p['source_fingerprint'],mode=p['mode'],
            policy=t['policy'],flags=POLICIES[t['policy']],project_hash=digest(project),
            effective_config_sha256=p['effective_config_hashes'][t['policy']]))
        grade=dict(sha='observed',hidden_pass=True,all_tests_pass=True,protected_preserved=True)
        result=dict(project=t['project'],policy=t['policy'],stages=[dict(stage=1,status='DONE',
            first=None,final=grade,correct_delivery=True),dict(stage=2,status='BLOCKED',
            first=None,final=None,correct_delivery=False)])
        atomic(path/'result.json',result)
        return p,path,result

    def test_absent_first_is_unknown_and_partial_trajectory_is_not_complete(self):
        from tools.ho02_report import report
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p,path,r=self.fixture(root)
            row=report(p,root)['rows'][0]
            self.assertIsNone(row['first']);self.assertEqual(row['first_bounds'],[0,1])
            self.assertEqual(row['first_coverage'],0)
            self.assertEqual(row['final'],.5);self.assertEqual(row['trajectory_final'],0)

    def test_duplicate_stages_and_forged_done_are_rejected(self):
        from tools.ho02_report import report
        from tools.ho02_support import atomic
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p,path,r=self.fixture(root)
            r['stages'][0]['status']='BLOCKED';atomic(path/'result.json',r)
            with self.assertRaises(ValueError):report(p,root)
            r['stages'][0]['status']='DONE';r['stages'][1]['stage']=1;atomic(path/'result.json',r)
            with self.assertRaises(ValueError):report(p,root)

    def test_foreign_project_and_duplicate_plan_cannot_count_twice(self):
        from tools.ho02_report import report
        from tools.ho02_support import atomic
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p,path,r=self.fixture(root)
            manifest=json.loads((path/'manifest.json').read_text());manifest['project_hash']='foreign'
            atomic(path/'manifest.json',manifest)
            with self.assertRaises(ValueError):report(p,root)
            p['trials'][1]=dict(p['trials'][0])
            with self.assertRaises(ValueError):report(p,root)

    def test_effective_configuration_is_pinned_without_state_path(self):
        from tools.ho02_project_run import effective_config,config_hash
        from tools.ho02_round import plan,validate
        from unittest.mock import patch
        from aa import config
        self.assertEqual(config_hash(effective_config('full','one')),config_hash(effective_config('full','two')))
        p=plan('config-pin',1)
        with patch.dict(config.DEFAULTS['retry'],max_model_calls=7):
            with self.assertRaises(ValueError):validate(p)


import os

class HO03WorkerIsolationTests(unittest.TestCase):
    def test_native_memory_controls_are_opt_in_and_do_not_relocate_auth(self):
        from unittest.mock import patch
        from aa.workers import Workers, LANES
        from aa.config import load
        with tempfile.TemporaryDirectory() as tmp:
            seen=[]
            def runner(cmd, **kw):
                seen.append((cmd,kw))
                return subprocess.CompletedProcess(cmd,0,'','')
            for flag in (False,True):
                cfg=load(overrides={'paths':{'state_dir':tmp},'harness_opt':{'codex_no_memories':flag}})
                w=Workers(cfg,runner=runner);w.verify_billing=lambda cli:None
                with patch.dict(os.environ,{'CODEX_HOME':'/existing/subscription/home'}):
                    w.execute(LANES['astra_high'],'fixture',Path(tmp),write=False)
                cmd,kw=seen[-1]
                for value in ('features.memories=false','memories.use_memories=false','memories.generate_memories=false'):
                    self.assertEqual(value in cmd,flag)
                self.assertEqual(kw['env']['CODEX_HOME'],'/existing/subscription/home')
                self.assertIn('read-only',cmd);self.assertIn('approval_policy="never"',cmd)
            self.assertEqual(seen[0][0][:5],seen[1][0][:5])

    def test_module_qualified_test_import_is_supported(self):
        p=subprocess.run([sys.executable,'-m','unittest','tests.test_aa_runtime.HO02ReviewTests'],
                         cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_corrupted_hook_is_audited_without_executing_it(self):
        from aa.stop_hook import install
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);wt=root/'wt';wt.mkdir()
            settings=install({}, {}, wt, root/'hooks',max_blocks=2,timeout_s=1,reason_template='fixture')
            command=settings['hooks']['Stop'][0]['hooks'][0]['command']
            capsule=next((root/'hooks').iterdir())
            (capsule/'hook.py').write_text("raise RuntimeError('must not execute')")
            p=subprocess.run(command,shell=True,input='{}',capture_output=True,text=True,timeout=5)
            self.assertEqual(json.loads(p.stdout),{})
            self.assertIn('hook_integrity_failed',(capsule/'events.jsonl').read_text())
            self.assertIn('integrity failed',p.stderr)


class HO03MeasurementRepairTests(unittest.TestCase):
    def test_missing_tier_cannot_be_resolved_by_checks_approval(self):
        from tools.ho03_support import owner_resolution
        t={'tier':None,'data':{'tier_votes':{'codex':None}}}
        self.assertEqual(owner_resolution(t,{'confirmed':False})[0],'handback')
        t['tier']='bounded'
        self.assertEqual(owner_resolution(t,{'confirmed':False}),('checks','ok'))
        self.assertEqual(owner_resolution(t,{'confirmed':True})[0],'handback')

    def test_deadline_counts_downtime_and_rejects_budget_extension(self):
        from tools.ho03_support import deadline
        p={};self.assertEqual(deadline(p,10,now=100),10)
        self.assertEqual(deadline(p,10,now=106),4)
        self.assertEqual(deadline(p,10,now=120),0)
        with self.assertRaises(ValueError):deadline(p,20,now=106)
        with self.assertRaises(ValueError):deadline(p,10,now=99)

    def test_protected_damage_is_new_once_but_taint_persists(self):
        from tools.ho03_support import preservation,protected_hashes
        with tempfile.TemporaryDirectory() as tmp:
            r=Path(tmp);(r/'data').write_text('original')
            before=protected_hashes(r,['data']);(r/'data').write_text('corrupt')
            first=preservation(r,{'data':'original'},before)
            self.assertEqual(first['protected_changed_this_stage'],['data'])
            second=preservation(r,{'data':'original'},protected_hashes(r,['data']))
            self.assertEqual(second['protected_changed_this_stage'],[])
            self.assertEqual(second['inherited_protected_damage'],['data'])
            self.assertFalse(second['protected_preserved'])

    def test_protection_and_handoff_do_not_follow_symlink_ancestors(self):
        from tools.ho03_support import safe_bytes
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';root.mkdir();outside=Path(tmp)/'outside';outside.mkdir()
            (outside/'value').write_text('must not read');(root/'link').symlink_to(outside,target_is_directory=True)
            self.assertIsNone(safe_bytes(root,'link/value'))
            self.assertIsNone(safe_bytes(root,'../outside/value'))

    def test_tough_route_produces_handoff_without_origin_or_worker(self):
        from tools.ho02_projects import catalog
        from tools.ho02_project_run import run_project
        from tools.ho03_support import verify_handoff
        def factory(cfg):return FakeWorkers(cfg,{'triage':triage('tough')})
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'trial'
            r=run_project(catalog()[0],root,'minimal',offline_handoff=True,worker_factory=factory)
            self.assertEqual(r['stages'][0]['status'],'AWAITING_PRO')
            self.assertFalse(r['stages'][0]['correct_delivery'])
            self.assertTrue(verify_handoff(root/'handoff-stage-1'))
            self.assertEqual(len([json.loads(x) for x in (root/'events.jsonl').read_text().splitlines() if json.loads(x)['kind']=='call_start']),1)

    def test_handoff_preserves_regular_untracked_work_and_rejects_tampering(self):
        from tools.ho02_project_run import git
        from tools.ho03_support import handoff,verify_handoff
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';root.mkdir();git(root,'init','-q');git(root,'config','user.name','lab');git(root,'config','user.email','lab@invalid')
            (root/'base').write_text('old');git(root,'add','.');git(root,'commit','-qm','base')
            (root/'notes').write_text('untracked work');out=Path(tmp)/'handoff'
            m=handoff(root,{'prompt':'review this','data':{}},out)
            self.assertIn('notes',m['files']);self.assertFalse(m['completion']);self.assertTrue(verify_handoff(out))
            (out/'snapshot/notes').write_text('changed')
            with self.assertRaises(ValueError):verify_handoff(out)
            m=handoff(root,{'prompt':'review this','data':{}},Path(tmp)/'small',max_bytes=0)
            self.assertFalse(m['mechanically_complete']);self.assertTrue(m['omitted'])

    def test_deferred_grading_and_strong_bounded_lane_ignore_tough_vote(self):
        from tools.ho02_projects import catalog,write_tree
        from tools.ho02_project_run import run_project
        p=catalog()[0];seen=[]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'trial'
            def factory(cfg):
                def work(lane,cwd,prompt,extra):
                    seen.append(lane.name)
                    self.assertEqual(list(root.glob('grade-stage-*/**/hidden.json')),[])
                    index=1 if 'customer now' in prompt else 0
                    write_tree(cwd,p['stages'][index]['reference'])
                    return Result(True,'done',{'status':'done','summary':'scripted producer','open_items':[],'question':''},[lane.model])
                return FakeWorkers(cfg,{'triage':triage('tough',peer='opus'),'work':work})
            r=run_project(p,root,'minimal','bounded',comparison_tier='medium_tough',defer_grading=True,worker_factory=factory)
            self.assertEqual(set(seen),{'astra_high'})
            self.assertTrue(all(s['correct_delivery'] for s in r['stages']))
            events=[json.loads(x)['kind'] for x in (root/'events.jsonl').read_text().splitlines()]
            self.assertIn('model_trajectory_ended',events)

    def test_ultra_and_middle_stage_contracts_are_executable_and_label_exposed_bridge(self):
        from tools.ho03_projects import catalog
        from tools.ho02_projects import validate_projects
        ps=catalog()
        self.assertEqual(len([p for p in ps if p['difficulty']=='ultra']),3)
        self.assertEqual(len({p['cluster'] for p in ps}),6)
        self.assertFalse(any(p['scenario'].get('fail_first_work') for p in ps))
        self.assertEqual(sum(p.get('exposed_bridge',False) for p in ps),1)
        results=validate_projects(ps)
        self.assertEqual(len(results),12)
        self.assertTrue(all(r['valid'] for r in results),results)


class HO03CalibrationTests(unittest.TestCase):
    def test_fixed_plan_counts_caps_and_settings_are_pinned(self):
        from tools.ho03_round import plan,validate
        sizes={'calibration':(12,24,14400),'extension':(42,84,43200),'upper-diagnostic':(6,12,10800),'routing':(3,3,4500)}
        for phase,expected in sizes.items():
            p=plan('fixed-'+phase,phase);validate(p)
            self.assertEqual((len(p['trials']),p['maximum_stage_runs'],p['wall_cap_s']),expected)
            if phase=='calibration':self.assertTrue(all(x['difficulty']=='middle' for x in p['trials'][:6]))
            p['wall_cap_s']+=1
            with self.assertRaises(ValueError):validate(p)

    def test_validity_gates_reject_ceiling_pooled_extremes_and_critical_override(self):
        from tools.ho03_round import plan,checkpoint,approve_checkpoint
        from tools.ho02_support import digest
        from unittest.mock import patch
        p=plan('gate');data=[dict(t,observed=True,unclosed_calls=[],new_protected_violations=0,critical_findings=0,final_correct=1,trajectory_correct=1) for t in p['trials']]
        with patch('tools.ho03_round.rows',return_value=data):
            c=checkpoint(p,Path('/unused'),6)
        self.assertTrue(c['mechanical_stop_reasons'])
        # The frozen middle-band endpoints are 20% and 80%, not rounded 15/85.
        for mean in (.18, .82):
            for r in data[:6]:r['final_correct']=mean
            with patch('tools.ho03_round.rows',return_value=data):c=checkpoint(p,Path('/unused'),6)
            self.assertIn('middle-band ceiling/floor; revise tasks, do not extend',c['mechanical_stop_reasons'])
        for i,r in enumerate(data[:6]):r['final_correct']=.5;r['trajectory_correct']=0
        data[0]['final_correct']=1;data[0]['trajectory_correct']=1;data[1]['final_correct']=0
        with patch('tools.ho03_round.rows',return_value=data):c=checkpoint(p,Path('/unused'),6)
        self.assertFalse(c['mechanical_stop_reasons'])
        audit=dict(checkpoint_sha256=digest(c),reviewer='test reviewer',evidence=['inspected all six traces'],no_personal_memory=True,no_evaluator_access=True,no_artifact_failures=True,no_critical_failures=True,trace_coverage_sufficient=True)
        approve_checkpoint(c,audit)
        data[0]['new_protected_violations']=1
        with patch('tools.ho03_round.rows',return_value=data):c=checkpoint(p,Path('/unused'),6)
        audit['checkpoint_sha256']=digest(c)
        with self.assertRaises(ValueError):approve_checkpoint(c,audit)

    def test_native_audit_cannot_replace_missing_memory_implementation(self):
        from tools.ho03_round import native_audit,plan
        from unittest.mock import patch
        p=plan('native');a=dict(source_fingerprint=p['source_fingerprint'],reviewer='operator',evidence=['installed CLI logs'],memory_injection_absent=True,subscription_auth_unchanged=True,node_available=True,cgroup_limits_verified=True,cli_versions={'codex':'observed','claude':'observed','node':'observed'})
        native_audit(a,p)
        with patch('tools.ho03_round.memory_implementation_available',return_value=False):
            with self.assertRaises(ValueError):native_audit(a,p)
        a['memory_injection_absent']='true'
        with self.assertRaises(ValueError):native_audit(a,p)

    def test_routing_only_never_calls_local_coding_worker(self):
        from tools.ho02_projects import catalog
        from tools.ho02_project_run import run_project
        def factory(cfg):return FakeWorkers(cfg,{'triage':triage('bounded')})
        with tempfile.TemporaryDirectory() as tmp:
            r=run_project(catalog()[0],Path(tmp)/'trial','minimal',offline_handoff=True,routing_only=True,defer_grading=True,worker_factory=factory)
            self.assertEqual(r['stages'][0]['status'],'ROUTED_LOCAL')
            self.assertIsNone(r['stages'][0]['final']);self.assertFalse(r['stages'][0]['correct_delivery'])

    def test_restoring_original_is_not_a_new_protected_violation(self):
        from tools.ho03_support import protected_hashes,preservation
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'f').write_text('damaged');before=protected_hashes(p,['f']);(p/'f').write_text('original')
            r=preservation(p,{'f':'original'},before)
            self.assertTrue(r['protected_preserved']);self.assertEqual(r['protected_changed_this_stage'],[])
            self.assertEqual(r['protected_files_changed'],['f'])

    def test_failed_triage_stays_unresolved_instead_of_dispatching_a_peer(self):
        from tools.ho02_project_run import run_project
        from tools.ho02_projects import catalog
        def factory(cfg):return FakeWorkers(cfg,{'triage':None})
        # Both triages must fail: keep a live local SemIf service on the host from voting.
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp, patch('aa.semif.SemIf.available', return_value=False):
            r=run_project(catalog()[0],Path(tmp)/'trial','minimal',worker_factory=factory)
            self.assertEqual(r['stages'][0]['status'],'WAIT_OWNER')
            self.assertIsNone(r['stages'][0]['task']['tier'])
            self.assertFalse(r['stages'][0]['correct_delivery'])


class HO03FinalGuardTests(unittest.TestCase):
    def test_report_keeps_missing_work_unknown_and_rejects_forged_completion(self):
        from tools.ho03_round import plan,rows
        from tools.ho03_projects import catalog
        from tools.ho01_round import POLICIES
        from tools.ho02_support import atomic,digest
        p=plan('report-probe');t=p['trials'][0];project=next(x for x in catalog() if x['id']==t['project'])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path=root/t['id'];path.mkdir()
            atomic(path/'manifest.json',dict(source_fingerprint=p['source_fingerprint'],project_hash=digest(project),policy=t['policy'],flags=POLICIES[t['policy']],mode=p['mode'],comparison_tier=p['comparison_tier'],offline_handoff=True,defer_grading=True,routing_only=False,timeout_s=t['timeout_s'],effective_config_sha256=p['effective_config_hashes'][t['policy']]))
            g=dict(sha='observed',hidden_pass=True,all_tests_pass=True,protected_preserved=True,protected_changed_this_stage=[])
            r=dict(project=t['project'],policy=t['policy'],stages=[dict(stage=1,status='DONE',first=None,final=g,correct_delivery=True,task={'tier':'medium_tough'})])
            atomic(path/'result.json',r);(path/'events.jsonl').write_text('')
            values=rows(p,root);self.assertEqual(values[0]['final_correct'],.5);self.assertIsNone(values[0]['first_correct']);self.assertFalse(values[1]['observed']);self.assertIsNone(values[1]['final_correct'])
            r['stages'][0]['status']='AWAITING_PRO';atomic(path/'result.json',r)
            with self.assertRaises(ValueError):rows(p,root)

    def test_extension_and_upper_diagnostic_require_their_explicit_calibration_link(self):
        from tools.ho03_round import plan,execute
        from tools.ho02_support import atomic
        from unittest.mock import patch
        for phase in ('extension','upper-diagnostic'):
            p=plan('missing-cal-'+phase,phase)
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);audit=root/'audit.json';versions={'codex':'c','claude':'a','node':'n'}
                atomic(audit,dict(source_fingerprint=p['source_fingerprint'],reviewer='operator',evidence=['fixture'],memory_injection_absent=True,subscription_auth_unchanged=True,node_available=True,cgroup_limits_verified=True,cli_versions=versions))
                with patch('tools.ho03_round.read_native_versions',return_value=versions),patch('tools.ho03_round.subprocess.Popen') as spawn:
                    with self.assertRaises(ValueError):execute(p,root/'runs',audit)
                    spawn.assert_not_called()
