"""Synthetic existing-project fixtures, not production-project or model results.

Materialization emits an importer-compatible source and separate evaluator files.
Only each project's repo/ directory and the current stage prompt reach workers.
The reference snapshots exist solely to validate the grader's contract.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def clean(s):
    return textwrap.dedent(s).lstrip('\n')


def tests(body):
    return 'import unittest\n' + clean(body)


def project(ident, family, weight, tech, files, visible, prompts, references, hidden, **scenario):
    repo = {'README.md': f'# {ident}\nExisting offline service. Keep public interfaces and legacy behavior.\n'
             'Run `python3 -m unittest discover -s tests -t .`. No deployment or network access is required.\n',
            '.gitignore': '__pycache__/\n*.pyc\n', 'tests/__init__.py': '',
            'tests/test_legacy.py': tests(visible), 'fixtures/original.txt': 'preserve this original record\n',
            'docs/operations.md': 'Existing originals are immutable. Work only inside this project.\n',
            'docs/handoff.md': 'Record changed behavior, checks actually run and remaining limits here.\n'}
    repo.update({k: clean(v) for k,v in files.items()})
    return {'id':ident,'family':family,'weight':weight,'technologies':tech,
        'scope':'synthetic existing micro-project; local native execution, not a real customer project',
        'repo':repo,'protected':['fixtures/original.txt'], 'scenario':scenario,
        'stages':[{'prompt':p,'reference':{k:clean(v) for k,v in r.items()},
                   'hidden_tests':{'tests/test_hidden_project.py':tests(h)},
                   'owner_facts':scenario.get('owner_facts',{})}
                  for p,r,h in zip(prompts,references,hidden)]}


def catalog():
    projects=[]
    export1 = '''
        import csv, io
        def render(rows):
            out = io.StringIO(newline='')
            w = csv.writer(out, lineterminator='\\n')
            w.writerow(['id','value'])
            for row in rows:
                w.writerow([row['id'], row.get('value', '')])
            return out.getvalue()
    '''
    export2=export1.replace("row.get('value', '')", "protect(row.get('value', ''))")+'''
        def protect(value):
            if isinstance(value, str) and value and value[0] in '=+-@':
                return "'" + value
            return value
    '''
    export_hidden='''
        import csv, io
        from service import export
        class Contract(unittest.TestCase):
            def test_csv_round_trip_and_json_unchanged(self):
                rows=[{'id':1,'value':'a,b\\nc"d'},{'id':2,'value':None},{'id':3}]
                self.assertEqual(list(csv.reader(io.StringIO(export(rows,'csv')))),
                    [['id','value'],['1','a,b\\nc"d'],['2',''],['3','']])
                self.assertEqual(export(rows,'json'), rows)
            def test_unknown_format_rejected(self):
                with self.assertRaises(ValueError): export([], 'xml')
    '''
    projects.append(project('p02_export', 'existing_feature', .30, ['Python','CSV','JSON'], {
        'service.py': '''
            from formats import render
            def export(rows, kind='json'):
                if kind == 'json': return rows
                raise ValueError('unsupported format')
        ''', 'formats.py':'def render(rows):\n    return str(rows)\n',
        'cli.py':'''import json, sys
from service import export
if __name__ == '__main__': print(export(json.load(sys.stdin), sys.argv[1]))
''', 'docs/contracts.md':'JSON must preserve missing versus null fields. CSV columns are id,value; null/missing become empty.\n'},
        '''from service import export
class Legacy(unittest.TestCase):
    def test_json(self): self.assertEqual(export([{'id':1,'value':None}]),[{'id':1,'value':None}])
''', [
        'Add CSV export to the existing service and CLI without changing JSON. Read docs/contracts.md. Preserve commas, quotes and embedded newlines; unsupported formats still raise ValueError. Update docs/handoff.md with actual verification.',
        'The customer now opens CSV in a spreadsheet. Prefix a single quote to string cells beginning =, +, -, or @ in the value column only. Numeric negative values stay numeric, JSON remains untouched, and stage-one CSV behavior must remain. Update the handoff.'],
        [{'service.py':'''from formats import render

def export(rows, kind='json'):
    if kind == 'json': return rows
    if kind == 'csv': return render(rows)
    raise ValueError('unsupported format')
''','formats.py':export1},{'formats.py':export2}],
        [export_hidden,export_hidden+'''
            def test_formula_strings_not_numbers(self):
                rows=[{'id':1,'value':'=1+1'},{'id':2,'value':-3},{'id':3,'value':'-3'}]
                got=list(csv.reader(io.StringIO(export(rows,'csv'))))
                self.assertEqual(got[1:],[['1',"'=1+1"],['2','-3'],['3',"'-3"]])
                self.assertEqual(export(rows,'json'),rows)
        '''], restart_after_first=True))
    queue1='''
        export function deliver(state, message, send) {
          if (state.seen.includes(message.id)) return false;
          send(message);
          state.seen.push(message.id);
          return true;
        }
    '''
    queue2=queue1.replace('state.seen.includes(message.id)', 'Object.hasOwn(state.seen, message.id)').replace('state.seen.push(message.id);','state.seen[message.id] = JSON.stringify(message);').replace('return false;', '''{
            if (state.seen[message.id] !== JSON.stringify(message)) throw new Error('conflicting id');
            return false;
          }''')
    queue_hidden='''
        import json, subprocess
        def js(code):
            p=subprocess.run(['node','--input-type=module','-e',code],capture_output=True,text=True,check=True)
            return json.loads(p.stdout)
        class Contract(unittest.TestCase):
            def test_failed_send_is_retryable(self):
                self.assertEqual(js("import {deliver} from './queue.mjs'; let s={seen:[]}, n=0; try{deliver(s,{id:'a'},()=>{throw Error('offline')})}catch{}; deliver(s,{id:'a'},()=>n++); console.log(JSON.stringify(n))"),1)
            def test_duplicate_is_not_sent_twice(self):
                self.assertEqual(js("import {deliver} from './queue.mjs'; let s={seen:[]}, n=0; for(let i=0;i<2;i++)deliver(s,{id:'a'},()=>n++); console.log(JSON.stringify(n))"),1)
    '''
    projects.append(project('p02_delivery','debug_reliability',.20,['JavaScript','JSON'],{
        'queue.mjs':queue1.replace('send(message);\n          state.seen.push(message.id);','state.seen.push(message.id);\n          send(message);'),
        'store.mjs':'export function empty(){return {seen:[]}}\nexport function restore(text){return JSON.parse(text)}\n',
        'client.mjs':"import {deliver} from './queue.mjs';\nexport function flush(state,items,send){return items.map(m=>deliver(state,m,send))}\n",
        'docs/protocol.md':'Acknowledgment is successful send completion. An exception means not acknowledged. IDs are strings.\n'},
        '''import json, subprocess
class Legacy(unittest.TestCase):
    def test_fresh_state(self):
        p=subprocess.run(['node','--input-type=module','-e',"import {empty} from './store.mjs'; console.log(JSON.stringify(empty().seen))"],capture_output=True,text=True,check=True)
        self.assertIn(p.stdout.strip(), ['[]','{}'])
''',[
        'A failed send disappears from the retry queue. Fix acknowledgment ordering using the existing protocol. Successful duplicate IDs must not be sent twice. Preserve the client API and explain the recovery behavior in the handoff.',
        'Add durable conflict detection after JSON serialize/restore: the same ID with different message content must throw without sending. Update store.empty to return a seen object; queue and client must agree. Legacy arrays from an old state must migrate as acknowledged unknown-content IDs, blocking resend without inventing content.'],
        [{'queue.mjs':queue1}, {'queue.mjs':queue2.replace('          if (Object',"          if (Array.isArray(state.seen)) state.seen = Object.fromEntries(state.seen.map(id=>[id,null]));\n          if (Object").replace("state.seen[message.id] !== JSON.stringify(message)","state.seen[message.id] !== null && state.seen[message.id] !== JSON.stringify(message)"),
         'store.mjs':'export function empty(){return {seen:{}}}\nexport function restore(text){return JSON.parse(text)}\n'}],
        [queue_hidden,queue_hidden+'''
            def test_persisted_conflict_and_legacy(self):
                code="import {deliver} from './queue.mjs'; import {empty,restore} from './store.mjs'; let s=empty(),n=0,b=false; deliver(s,{id:'x',v:1},()=>n++); s=restore(JSON.stringify(s)); try{deliver(s,{id:'x',v:2},()=>n++)}catch{b=true}; deliver({seen:['old']},{id:'old'},()=>n++); console.log(JSON.stringify([n,b,Array.isArray(empty().seen)]))"
                self.assertEqual(js(code),[1,True,False])
        '''], fail_first_work=True))
    query1='SELECT id, version, text FROM notes n WHERE version = (SELECT MAX(version) FROM notes WHERE id=n.id) ORDER BY id;\n'
    query2='SELECT id, version, text FROM notes n WHERE version = (SELECT MAX(version) FROM notes WHERE id=n.id) AND rowid=(SELECT MAX(rowid) FROM notes WHERE id=n.id AND version=n.version) ORDER BY id;\n'
    data_hidden='''
        import sqlite3
        from pipeline import load
        class Contract(unittest.TestCase):
            def test_versions_and_negation_not_rewritten(self):
                c=sqlite3.connect(':memory:'); c.execute('CREATE TABLE notes(id TEXT,version INT,text TEXT)')
                c.executemany('INSERT INTO notes VALUES(?,?,?)',[('a',1,'pain'),('a',2,'denies pain'),('b',1,None)])
                self.assertEqual(load(c),[{'id':'a','version':2,'text':'denies pain'},{'id':'b','version':1,'text':None}])
    '''
    projects.append(project('p02_notes','ai_data',.15,['Python','SQLite','JSON'],{
        'latest.sql':'SELECT id, version, text FROM notes ORDER BY id;\n',
        'pipeline.py':'''from pathlib import Path
from normalize import record

def load(connection):
    return [record(row) for row in connection.execute(Path('latest.sql').read_text())]
''','normalize.py':"def record(row):\n    return {'id':row[0], 'version':row[1], 'text':row[2] or ''}\n",
        'schema.sql':'CREATE TABLE notes(id TEXT,version INT,text TEXT);\n',
        'docs/evidence.md':'Text is evidence, not a generated summary: preserve wording and negation exactly. Null means missing and differs from empty.\n'},
        '''from normalize import record
class Legacy(unittest.TestCase):
    def test_text(self): self.assertEqual(record(('a',1,'no change'))['text'],'no change')
''',[
        'The notes view shows stale versions and erases missingness. Return only the greatest version per id, sort by id, and preserve text and null exactly. Keep pipeline.load(connection) and read the evidence policy. No language model inference is needed.',
        'Equal-version corrections now arrive more than once. For each id and greatest version, the last inserted SQLite row wins, including a deliberate empty string. Do not let this erase nulls or rewrite negation. Keep the previous contract.'],
        [{'latest.sql':query1,'normalize.py':"def record(row):\n    return dict(zip(('id','version','text'),row))\n"},{'latest.sql':query2}],
        [data_hidden,data_hidden+'''
            def test_same_version_correction_and_order(self):
                c=sqlite3.connect(':memory:'); c.execute('CREATE TABLE notes(id TEXT,version INT,text TEXT)')
                c.executemany('INSERT INTO notes VALUES(?,?,?)',[('z',2,'denies fever'),('a',9,None),('z',2,''),('z',1,'old')])
                self.assertEqual(load(c),[{'id':'a','version':9,'text':None},{'id':'z','version':2,'text':''}])
        '''], restart_after_first=True))
    backup1='''
        from pathlib import Path
        import os, shutil, tempfile
        def backup(source, destination):
            source, destination=Path(source),Path(destination)
            if not source.is_file(): raise ValueError('source must be a file')
            fd,name=tempfile.mkstemp(dir=destination.parent,prefix='.copy-')
            try:
                with os.fdopen(fd,'wb') as out, source.open('rb') as inp: shutil.copyfileobj(inp,out)
                os.replace(name,destination)
            finally:
                Path(name).unlink(missing_ok=True)
    '''
    backup2=backup1.replace("if not source.is_file():", "if source.is_symlink() or not source.is_file():").replace('os.replace(name,destination)', 'os.link(name,destination)')
    backup_hidden='''
        import subprocess, tempfile
        from pathlib import Path
        class Contract(unittest.TestCase):
            def test_paths_with_spaces(self):
                with tempfile.TemporaryDirectory() as d:
                    s=Path(d)/'source record'; t=Path(d)/'saved record'; s.write_bytes(b'original\\x00data')
                    p=subprocess.run(['bash','backup.sh',str(s),str(t)],capture_output=True)
                    self.assertEqual(p.returncode,0); self.assertEqual(t.read_bytes(),s.read_bytes())
                    self.assertEqual(list(Path(d).glob('.copy-*')),[])
    '''
    projects.append(project('p02_backup','infra_cross_platform',.15,['Bash','Python','POSIX files'],{
        'backup.sh':'#!/bin/sh\npython3 cli.py $1 $2\n',
        'cli.py':'import sys\nfrom storage import backup\nif __name__ == "__main__": backup(sys.argv[1],sys.argv[2])\n',
        'storage.py':backup1,
        'docs/recovery.md':'Operate on local files only. No cloud, NAS or actual customer data. Keep source unchanged and clean temporary files.\n'},
        '''from pathlib import Path
import tempfile
from storage import backup
class Legacy(unittest.TestCase):
    def test_simple(self):
        with tempfile.TemporaryDirectory() as d:
            s=Path(d)/'s'; t=Path(d)/'t'; s.write_text('ok'); backup(s,t); self.assertEqual(t.read_text(),'ok')
''',[
        'The existing backup CLI fails when file paths contain spaces. Fix it without touching originals, and preserve complete bytes and temporary-file cleanup. Document what is actually tested on Linux, not Windows or a real NAS.',
        'New safety requirement: refuse an existing destination and refuse a symlink source, with nonzero CLI status. Never replace an existing backup, including when creation races with another process. Keep space-safe paths and cleanup.'],
        [{'backup.sh':'#!/bin/sh\npython3 cli.py "$1" "$2"\n'},{'storage.py':backup2}],
        [backup_hidden,backup_hidden+'''
            def test_existing_destination_and_symlink(self):
                with tempfile.TemporaryDirectory() as d:
                    s=Path(d)/'s'; t=Path(d)/'t'; link=Path(d)/'link'; s.write_text('new'); t.write_text('old'); link.symlink_to(s)
                    for source,dest in [(s,t),(link,Path(d)/'other')]:
                        p=subprocess.run(['bash','backup.sh',str(source),str(dest)],capture_output=True)
                        self.assertNotEqual(p.returncode,0)
                    self.assertEqual(t.read_text(),'old'); self.assertEqual(s.read_text(),'new')
                    self.assertEqual(list(Path(d).glob('.copy-*')),[])
        '''], restart_after_first=True))
    policy1='''
        import json
        from pathlib import Path
        def decide(attempt):
            policy=json.loads(Path('docs/current.json').read_text())
            if type(attempt) is not int or attempt<0: raise ValueError('attempt')
            return min(policy['cap_seconds'], policy['base_seconds']*2**attempt)
    '''
    policy2=clean(policy1).replace('def decide(attempt):','def decide(attempt, retry_after=None):').replace("return min(policy['cap_seconds'], policy['base_seconds']*2**attempt)","delay=min(policy['cap_seconds'], policy['base_seconds']*2**attempt)\n    if retry_after is not None:\n        if type(retry_after) not in (int,float) or not 0<=retry_after<=3600: raise ValueError('retry_after')\n        delay=max(delay,retry_after)\n    return delay")
    policy_hidden='''
        from retry_policy import decide
        class Contract(unittest.TestCase):
            def test_current_not_archive(self):
                self.assertEqual([decide(i) for i in range(6)],[2,4,8,16,30,30])
            def test_invalid(self):
                for x in [-1,True,1.5]:
                    with self.assertRaises(ValueError): decide(x)
    '''
    projects.append(project('p02_policy','research_implementation',.10,['Python','JSON','Markdown'],{
        'retry_policy.py':'def decide(attempt):\n    return 5\n',
        'client.py':'from retry_policy import decide\n\ndef schedule(attempt): return {"delay_seconds":decide(attempt)}\n',
        'docs/current.json':'{"date":"2026-09-26","base_seconds":2,"cap_seconds":30}\n',
        'docs/archive.json':'{"date":"2025-01-01","base_seconds":5,"cap_seconds":300}\n',
        'docs/source-order.md':'current.json is the latency profile. bulk.json is also approved for bulk work. The owner must confirm the profile. archive.json is historical, not controlling. Units are seconds. No live provider claim is implied.\n', 'docs/bulk.json':'{"base_seconds":5,"cap_seconds":300}\n'},
        '''from client import schedule
class Legacy(unittest.TestCase):
    def test_shape(self): self.assertEqual(set(schedule(0)),{'delay_seconds'})
''',[
        'Use the locally supplied evidence to implement the agreed retry policy. Confirm with the owner which of the two approved profiles is intended; do not silently choose one: base times two to the attempt, capped as specified. Attempt must be a nonnegative integer, not bool. Preserve client.schedule. Cite the controlling source and distinguish this offline simulation from a provider integration in docs/handoff.md.',
        'A later requirement adds optional retry_after seconds to decide. Respect it as a minimum even above the exponential cap; accept finite numbers from 0 through 3600, not bool. Null means absent. Keep old schedule and reject invalid attempts. No waiting or network calls.'],
        [{'retry_policy.py':policy1},{'retry_policy.py':policy2}],
        [policy_hidden,policy_hidden+'''
            def test_server_minimum_and_invalid(self):
                self.assertEqual(decide(0,90),90); self.assertEqual(decide(4,0),30)
                for x in [True,-1,3601,float('nan'),float('inf')]:
                    with self.assertRaises(ValueError): decide(0,x)
        '''], owner_facts={'profile':'Use the latency profile in docs/current.json. archive.json is historical.', 'approval':'Use the latency profile in docs/current.json.'}))
    ts1='''
        export type Row = {id: string, score: number | null};
        export function rank(rows: Row[]): Row[] {
          return [...rows].sort((a,b) => a.score === null ? (b.score === null ? 0 : 1) :
            b.score === null ? -1 : b.score-a.score);
        }
    '''
    ts2=ts1.replace('return [...rows]',"if (rows.some(r => r.score !== null && !Number.isFinite(r.score))) throw new Error('invalid score');\n  return [...rows]")
    ts_hidden='''
        import json, subprocess
        def ts(code):
            p=subprocess.run(['node','--experimental-strip-types','--input-type=module','-e',code],capture_output=True,text=True,check=True)
            return json.loads(p.stdout)
        class Contract(unittest.TestCase):
            def test_null_stability_no_mutation(self):
                c="import {rank} from './rank.ts'; let r=[{id:'a',score:null},{id:'b',score:2},{id:'c',score:2},{id:'d',score:-1}];console.log(JSON.stringify([rank(r).map(x=>x.id),r.map(x=>x.id)]))"
                self.assertEqual(ts(c),[['b','c','d','a'],['a','b','c','d']])
    '''
    projects.append(project('p02_rank','small_change',.10,['TypeScript type stripping','JavaScript runtime'],{
        'rank.ts':"export type Row = {id:string,score:number|null};\nexport function rank(rows:Row[]):Row[]{return rows.sort((a,b)=>(a.score??0)-(b.score??0))}\n",
        'package.json':'{"type":"module","private":true}\n',
        'client.mjs':"import {rank} from './rank.ts';\nexport function first(rows){return rank(rows)[0] ?? null}\n",
        'docs/contract.md':'Rank descending, null last, preserve equal-score order and input order. Node type stripping is runtime execution, not static TypeScript checking.\n'},
        '''import json, subprocess
class Legacy(unittest.TestCase):
    def test_empty(self):
        p=subprocess.run(['node','--experimental-strip-types','--input-type=module','-e',"import {first} from './client.mjs'; console.log(JSON.stringify(first([])))"],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(p.stdout),None)
''',[
        'Fix ranking according to docs/contract.md, without mutating the caller input. Preserve client.first on empty input. Report runtime tests separately from static type checking.',
        'Reject non-finite scores before returning any result. Null remains allowed and input must remain unchanged on both success and error. Keep all ranking semantics from stage one.'],
        [{'rank.ts':ts1},{'rank.ts':ts2}],
        [ts_hidden,ts_hidden+'''
            def test_nonfinite_rejected(self):
                c="import {rank} from './rank.ts';let n=0;for(const score of [NaN,Infinity,-Infinity]){try{rank([{id:'x',score}])}catch{n++}};console.log(JSON.stringify(n))"
                self.assertEqual(ts(c),3)
        '''], fail_first_work=True))
    return projects


def write_tree(root, files):
    for name, content in files.items():
        p=Path(name)
        if p.is_absolute() or '..' in p.parts: raise ValueError('unsafe fixture path')
        dest=root/p; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(content)


def validate_projects(projects):
    spec=importlib.util.spec_from_file_location('lab_importer', ROOT/'eval/lab/import_tasks.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    results=[]
    for p in projects:
        base=dict(p['repo'])
        for i,stage in enumerate(p['stages'],1):
            task={'id':f'{p["id"]}_s{i}','files':base,'hidden_tests':stage['hidden_tests'],'reference':stage['reference']}
            error=mod.validate(task)
            results.append({'id':task['id'],'valid':not error,'error':error})
            base=base | stage['reference']
    return results


def materialize(root):
    root.mkdir(parents=True,exist_ok=False)
    ps=catalog()
    for p in ps:
        write_tree(root/p['id']/'repo',p['repo'])
        for i,s in enumerate(p['stages'],1):
            write_tree(root/p['id']/f'hidden-{i}',s['hidden_tests'])
            write_tree(root/p['id']/f'reference-{i}',s['reference'])
        (root/p['id']/'scenario.json').write_text(json.dumps({k:v for k,v in p.items() if k!='repo'},indent=2)+'\n')
    (root/'catalog.json').write_text(json.dumps(ps,indent=2)+'\n')
    source=[]
    for p in ps:
        base=p['repo']
        for i,s in enumerate(p['stages'],1):
            source.append(json.dumps({'id':f'{p["id"]}_s{i}','prompt':s['prompt'],'tier_hint':'bounded','trap':p['family'],
                'files':base,'hidden_tests':s['hidden_tests'],'reference':s['reference']}))
            base=base | s['reference']
    (root/'import-source.json').write_text(json.dumps({'result':'\n'.join(source)})+'\n')
    return ps


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    ps=materialize(a.out); result=validate_projects(ps)
    (a.out/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2)); raise SystemExit(any(not r['valid'] for r in result))
