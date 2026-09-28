"""Preregistered stress catalog: three middle probes and three upper-edge projects.

All data is synthetic. Difficulty labels predict native-worker outcomes; they are
not measurements. Hidden/reference material is evaluator-only by protocol.
"""
from __future__ import annotations
import argparse
import copy
import json
from pathlib import Path
from tools.ho02_projects import project, catalog as old_catalog, validate_projects, write_tree
from tools.ho02_support import digest, atomic
from tools.ho03_jobs import build as jobs
from tools.ho03_temporal import build as temporal
from tools.ho03_restore import build as restore

TRANSCRIPT_CONTRACT = '''# Source-grounded note assembly
The existing pipeline consumes complete source segments (id, text) and model
claims (segment, start, end, label). Offsets are Python Unicode code-point offsets
in the original segment, half-open; never offsets in a stripped or normalized copy.
Labels are exactly finding, plan, or uncertainty. Validate the whole input before
returning anything. Segments have unique nonempty string IDs and string text.
Claims have exactly the four keys above. start/end must be integers, not booleans,
and 0 <= start < end <= len(text). Unknown segments/labels and extra keys fail.
Return one note per distinct (segment,start,end,label), in source-segment order,
then start,end,label order. Each note has exactly those fields plus quote containing
the exact substring. Do not infer missing facts, remove negation, translate, or
normalize quotations. Inputs must not be mutated. A known empty claim list returns
[]. The API and command-line export must use the same implementation.
'''
TRANSCRIPT_REF = '''from .contracts import LABELS

def assemble(segments,claims):
    if not isinstance(segments,list) or not isinstance(claims,list):raise ValueError('lists required')
    sources={};order={}
    for i,s in enumerate(segments):
        if not isinstance(s,dict) or set(s)!={'id','text'} or not isinstance(s['id'],str) or not s['id'] or not isinstance(s['text'],str) or s['id'] in sources:raise ValueError('source segment')
        sources[s['id']]=s['text'];order[s['id']]=i
    out={}
    for c in claims:
        if not isinstance(c,dict) or set(c)!={'segment','start','end','label'}:raise ValueError('claim fields')
        if not isinstance(c['segment'],str) or c['segment'] not in sources or not isinstance(c['label'],str) or c['label'] not in LABELS:raise ValueError('claim source/label')
        a,b=c['start'],c['end'];text=sources[c['segment']]
        if type(a) is not int or type(b) is not int or not 0<=a<b<=len(text):raise ValueError('offsets')
        key=(c['segment'],a,b,c['label']);out[key]=dict(c,quote=text[a:b])
    return [out[k] for k in sorted(out,key=lambda k:(order[k[0]],k[1],k[2],k[3]))]
'''
RECONCILE_REF = '''from .assemble import assemble

def reconcile(segments,events):
    if not isinstance(events,list):raise ValueError('events required')
    known={};latest={}
    for e in events:
        if not isinstance(e,dict) or set(e)!={'id','revision','deleted','claim'} or not isinstance(e['id'],str) or not e['id'] or type(e['revision']) is not int or e['revision']<1 or type(e['deleted']) is not bool:raise ValueError('event')
        if e['deleted']:
            if e['claim'] is not None:raise ValueError('deleted claim must be null')
        else:assemble(segments,[e['claim']])
        key=(e['id'],e['revision'])
        if key in known and known[key]!=e:raise ValueError('conflicting replay')
        known[key]=e
        if e['id'] not in latest or e['revision']>latest[e['id']]['revision']:latest[e['id']]=e
    return assemble(segments,[e['claim'] for e in latest.values() if not e['deleted']])
'''

def transcript():
    h1='''import copy
from notes.api import build_note
class Contract(unittest.TestCase):
 def test_grounding_order_and_no_mutation(self):
  s=[{'id':'z','text':'  No fever. 🐋 plan.'},{'id':'a','text':'second'}]
  cs=[{'segment':'a','start':0,'end':6,'label':'finding'},{'segment':'z','start':2,'end':10,'label':'finding'},{'segment':'z','start':2,'end':10,'label':'finding'}]
  old=copy.deepcopy((s,cs));r=build_note(s,cs)
  self.assertEqual([x['quote'] for x in r],['No fever','second']);self.assertEqual((s,cs),old)
  self.assertEqual(build_note(s,[]),[])
 def test_entire_input_validation(self):
  s=[{'id':'x','text':'abc'}];good={'segment':'x','start':0,'end':1,'label':'plan'}
  for patch in ({'start':True},{'end':4},{'start':-1},{'end':0},{'label':'diagnosis'},{'segment':'absent'},{'extra':0}):
   with self.subTest(patch=patch),self.assertRaises(ValueError):build_note(s,[good,dict(good,**patch)])
  with self.assertRaises(ValueError):build_note(s+s,[])
 def test_unicode_offsets(self):
  r=build_note([{'id':'x','text':'🦉é no'}],[{'segment':'x','start':1,'end':3,'label':'uncertainty'}])
  self.assertEqual(r[0]['quote'],'é')
'''
    h2='''from notes.api import build_note,build_revision
class Revision(unittest.TestCase):
 def setUp(self):
  self.s=[{'id':'x','text':'no pain; follow up'}];self.c={'segment':'x','start':0,'end':7,'label':'finding'}
 def e(self,rev,deleted=False):return {'id':'n','revision':rev,'deleted':deleted,'claim':None if deleted else self.c}
 def test_out_of_order_tombstone_does_not_resurrect(self):
  self.assertEqual(build_revision(self.s,[self.e(3,True),self.e(1),self.e(2),self.e(3,True)]),[])
  self.assertEqual(build_revision(self.s,[self.e(2),self.e(1)]),build_note(self.s,[self.c]))
 def test_conflicts_and_invalid_old_events_not_silently_ignored(self):
  with self.assertRaises(ValueError):build_revision(self.s,[self.e(2),self.e(2,True)])
  bad=dict(self.e(1),claim=dict(self.c,start=-1))
  with self.assertRaises(ValueError):build_revision(self.s,[self.e(3,True),bad])
  with self.assertRaises(ValueError):build_revision(self.s,[dict(self.e(1),revision=True)])
 def test_duplicate_claims_collapse_across_ids(self):
  self.assertEqual(len(build_revision(self.s,[self.e(1),dict(self.e(2),id='other')])),1)
'''
    p=project('m03_transcript','ai_data',1/6,['Python','JSON','Markdown'],{
        'notes/__init__.py':'','notes/contracts.py':"LABELS={'finding','plan','uncertainty'}\n",
        'notes/assemble.py':"def assemble(segments,claims):\n return [dict(c,quote=next(s['text'] for s in segments if s['id']==c['segment']).strip()[c['start']:c['end']]) for c in claims]\n",
        'notes/revisions.py':'def reconcile(segments,events):\n return []\n',
        'notes/api.py':'from .assemble import assemble\nfrom .revisions import reconcile\nbuild_note=assemble\nbuild_revision=reconcile\n',
        'export.py':"import json,sys\nfrom notes.api import build_note\nif __name__=='__main__':\n d=json.load(sys.stdin);print(json.dumps(build_note(d['segments'],d['claims']),ensure_ascii=False))\n",
        'docs/source-contract.md':TRANSCRIPT_CONTRACT,
        'docs/old-proposal.md':'Historical only: stripping whitespace was proposed before offset correctness was required. Do not treat this as the current contract.\n',
        'config.json':'{"mode":"source-grounded","infer_missing":false}\n'},
        "from notes.api import build_note\nclass Legacy(unittest.TestCase):\n def test_basic(self):\n  self.assertEqual(build_note([{'id':'x','text':'yes'}],[{'segment':'x','start':0,'end':3,'label':'finding'}])[0]['quote'],'yes')\n",
        ['Make note assembly reliable and source-grounded throughout the existing interfaces. Follow docs/source-contract.md; preserve unrelated files and explain verification.',
         'Add revision-aware note assembly through build_revision(segments,events). Each event has exactly id (nonempty string), revision (positive integer, not bool), deleted (bool), claim (a valid original claim, or null only when deleted). Select the greatest revision per id regardless of arrival order. Exact duplicates are idempotent; conflicting same-id/revision rows fail. Validate ALL events including superseded events. A tombstone removes the note without falling back to an earlier claim. Return the original assemble output for active claims, retaining all original grounding and dedup rules. Preserve build_note and document the new interface.'],
        [{'notes/assemble.py':TRANSCRIPT_REF},{'notes/revisions.py':RECONCILE_REF}],[h1,h2],restart_after_first=True)
    p.update(difficulty='middle',cluster='grounded_notes',predicted_single_pass=[.25,.8],budget_seconds=600)
    return p

INGEST_CONTRACT='''# Current incremental import contract
Importer(path) opens durable SQLite state. apply(batch, rows) accepts a nonempty
string batch ID and a list of rows with exactly id, cents, tags. id is a nonempty
string; cents is an integer (not bool); tags is a list of distinct nonempty strings.
An ID may appear at most once in a batch. A successful batch completely upserts
those invoices and REPLACES their tags, including an empty tag list. rows() returns
sorted id,cents rows; summary() sums cents once per invoice, not once per tag.
Replaying an identical batch with different row or tag order is a no-op. Reusing its
ID for different normalized content raises ValueError, even after restart. Validate
all input before changing anything. Invoice/tag/receipt changes must be one atomic
transaction. Never delete unrelated invoices or notes. Stage-1 legacy entry points
remain available. Do not change schema or notes just to make a test pass.
'''
INGEST_SCHEMA='''CREATE TABLE IF NOT EXISTS invoices(id TEXT PRIMARY KEY,cents INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS tags(id TEXT NOT NULL,tag TEXT NOT NULL,PRIMARY KEY(id,tag));
CREATE TABLE IF NOT EXISTS receipts(batch TEXT PRIMARY KEY,payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS notes(id TEXT PRIMARY KEY,text TEXT NOT NULL);
'''
INGEST_REF='''import sqlite3,json
from pathlib import Path

def normalized(rows):
 if not isinstance(rows,list):raise ValueError('rows')
 seen=set();out=[]
 for r in rows:
  if not isinstance(r,dict) or set(r)!={'id','cents','tags'} or not isinstance(r['id'],str) or not r['id'] or r['id'] in seen or type(r['cents']) is not int or not isinstance(r['tags'],list):raise ValueError('invoice')
  if any(not isinstance(x,str) or not x for x in r['tags']) or len(set(r['tags']))!=len(r['tags']):raise ValueError('tags')
  seen.add(r['id']);out.append(dict(r,tags=sorted(r['tags'])))
 return sorted(out,key=lambda r:r['id'])

class Importer:
 def __init__(self,path):
  self.db=sqlite3.connect(path,isolation_level=None);self.db.executescript(Path(__file__).with_name('schema.sql').read_text())
 def close(self):self.db.close()
 def apply(self,batch,rows):
  if not isinstance(batch,str) or not batch:raise ValueError('batch')
  rows=normalized(rows);payload=json.dumps(rows,sort_keys=True,separators=(',',':'))
  self.db.execute('BEGIN IMMEDIATE')
  try:
   old=self.db.execute('SELECT payload FROM receipts WHERE batch=?',(batch,)).fetchone()
   if old:
    if old[0]!=payload:raise ValueError('conflicting batch replay')
   else:
    for r in rows:
     self.db.execute('INSERT INTO invoices VALUES(?,?) ON CONFLICT(id) DO UPDATE SET cents=excluded.cents',(r['id'],r['cents']))
     self.db.execute('DELETE FROM tags WHERE id=?',(r['id'],))
     self.db.executemany('INSERT INTO tags VALUES(?,?)',[(r['id'],tag) for tag in r['tags']])
    self.db.execute('INSERT INTO receipts VALUES(?,?)',(batch,payload))
  except BaseException:self.db.rollback();raise
  else:self.db.commit()
 def rows(self):return [dict(id=i,cents=c) for i,c in self.db.execute('SELECT id,cents FROM invoices ORDER BY id')]
 def summary(self):return self.db.execute('SELECT COALESCE(SUM(cents),0) FROM invoices').fetchone()[0]
 def page(self,after=None,limit=2):
  if type(limit) is not int or limit<1:raise ValueError('limit')
  if after is not None and not isinstance(after,str):raise ValueError('cursor')
  sql='SELECT id,cents FROM invoices'+(' WHERE id>?' if after is not None else '')+' ORDER BY id LIMIT ?'
  args=(after,limit+1) if after is not None else (limit+1,)
  rows=[dict(id=i,cents=c) for i,c in self.db.execute(sql,args)];more=len(rows)>limit;rows=rows[:limit]
  return {'rows':rows,'next':rows[-1]['id'] if more else None}
'''

def ingest():
    base='''import sqlite3
from pathlib import Path
class Importer:
 def __init__(self,path):
  self.db=sqlite3.connect(path);self.db.executescript(Path(__file__).with_name('schema.sql').read_text())
 def close(self):self.db.close()
 def apply(self,batch,rows):
  for r in rows:
   self.db.execute('INSERT OR REPLACE INTO invoices VALUES(?,?)',(r['id'],r['cents']))
   for tag in r['tags']:self.db.execute('INSERT OR IGNORE INTO tags VALUES(?,?)',(r['id'],tag))
   self.db.commit()
 def rows(self):return [dict(id=i,cents=c) for i,c in self.db.execute('SELECT id,cents FROM invoices ORDER BY id')]
 def summary(self):return self.db.execute('SELECT COALESCE(SUM(cents),0) FROM invoices LEFT JOIN tags USING(id)').fetchone()[0]
 def page(self,after=None,limit=2):return {'rows':self.rows()[:limit],'next':None}
'''
    common='''import tempfile,sqlite3
from pathlib import Path
from importer import Importer
class Contract(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db';self.s=Importer(self.path)
 def tearDown(self):self.s.close();self.tmp.cleanup()
 def row(self,i='a',c=10,tags=None):return {'id':i,'cents':c,'tags':[] if tags is None else tags}
'''
    h1=common+''' def test_replace_tags_and_cardinality(self):
  self.s.apply('a',[self.row(tags=['x','y']),self.row('b',-2)])
  self.assertEqual(self.s.summary(),8)
  self.s.apply('b',[self.row(c=11)])
  self.assertEqual(self.s.summary(),9);self.assertEqual(list(self.s.db.execute("SELECT * FROM tags WHERE id='a'")),[])
 def test_replay_normalization_restart_and_conflict(self):
  rows=[self.row(tags=['y','x']),self.row('b',3)]
  self.s.apply('batch',rows);self.s.close();self.s=Importer(self.path)
  self.s.apply('batch',[rows[1],dict(rows[0],tags=['x','y'])])
  with self.assertRaises(ValueError):self.s.apply('batch',[self.row(c=99)])
  self.assertEqual(self.s.summary(),13)
 def test_validation_and_transaction_rollback(self):
  self.s.apply('start',[self.row('old',8)])
  for bad in (self.row(c=True),self.row(tags=['x','x']),dict(self.row(),extra=1)):
   with self.assertRaises(ValueError):self.s.apply('bad',[self.row('new',2),bad])
   self.assertEqual(self.s.rows(),[{'id':'old','cents':8}])
  self.s.db.execute("CREATE TRIGGER stop_receipt BEFORE INSERT ON receipts BEGIN SELECT RAISE(ABORT,'inject');END")
  with self.assertRaises(sqlite3.DatabaseError):self.s.apply('failure',[self.row('new',2)])
  self.assertEqual(self.s.rows(),[{'id':'old','cents':8}])
'''
    # Stage one deliberately leaves the old page implementation. The requested
    # stage-two keyset contract therefore fails on a valid stage-one reference.
    ref1=INGEST_REF[:INGEST_REF.index(' def page')]+" def page(self,after=None,limit=2):return {'rows':self.rows()[:limit],'next':None}\n"
    h2=common+''' def test_keyset_pages_have_no_duplicates_or_phantom_next(self):
  self.s.apply('a',[self.row('a'),self.row('c'),self.row('e'),self.row('g')])
  first=self.s.page(limit=2);self.assertEqual(first['next'],'c')
  self.s.apply('b',[self.row('b'),self.row('d')])
  second=self.s.page(after=first['next'],limit=2)
  self.assertEqual([r['id'] for r in second['rows']],['d','e']);self.assertEqual(second['next'],'e')
  last=self.s.page(after='e',limit=2);self.assertEqual([r['id'] for r in last['rows']],['g']);self.assertIsNone(last['next'])
  self.assertEqual(self.s.page(after='z'),{'rows':[],'next':None})
 def test_cursor_does_not_need_to_exist_and_validation(self):
  self.s.apply('a',[self.row('a'),self.row('c')]);self.assertEqual(self.s.page(after='b')['rows'],[{'id':'c','cents':10}])
  for value in (True,0,-1,'2'):
   with self.assertRaises(ValueError):self.s.page(limit=value)
 def test_old_contract_still_holds(self):
  self.s.apply('a',[self.row(tags=['x','y'])]);self.assertEqual(self.s.summary(),10)
  with self.assertRaises(ValueError):self.s.apply('a',[self.row(c=11)])
'''
    p=project('m03_ingest','debug_reliability',1/6,['Python','SQLite','SQL','JSON'],{
        'importer.py':base,'schema.sql':INGEST_SCHEMA,
        'api.py':'from importer import Importer\ndef total(store): return store.summary()\n',
        'batch.py':'def run(store,batch_id,rows):\n store.apply(batch_id,rows)\n return store.rows()\n',
        'reports/monthly.sql':'SELECT COALESCE(SUM(cents),0) FROM invoices;\n',
        'docs/current-contract.md':INGEST_CONTRACT,
        'docs/incident.md':'Totals increase when more tags are added. Repeated imports sometimes leave stale labels. Prior successful batches and unrelated notes must survive a failed import.\n'},
        "import tempfile\nfrom pathlib import Path\nfrom importer import Importer\nclass Legacy(unittest.TestCase):\n def test_basic(self):\n  with tempfile.TemporaryDirectory() as t:\n   s=Importer(Path(t)/'db');s.apply('x',[{'id':'a','cents':3,'tags':[]}]);self.assertEqual(s.rows(),[{'id':'a','cents':3}]);s.close()\n",
        ['Investigate and repair the reporting/import reliability problems in this repository. Follow docs/current-contract.md, preserve prior data and unrelated work, and document the verified cause.',
         'The existing API now needs page(after=None,limit=2): return rows ordered by binary ID, strictly after the cursor (which need not exist), with at most limit rows, and next equal to the last returned ID only when more rows exist; otherwise null. limit is a positive integer, not bool. after is null or a string. Use keyset semantics so inserted earlier IDs do not shift later pages; this is not a frozen snapshot. Retain all stage-one import, replay, transaction and total contracts.'],
        [{'importer.py':ref1},{'importer.py':INGEST_REF}],[h1,h2],restart_after_first=True)
    p.update(difficulty='middle',cluster='incremental_import',predicted_single_pass=[.2,.75],budget_seconds=600)
    return p


def catalog():
    bridge=copy.deepcopy(next(p for p in old_catalog() if p['id']=='p02_policy'))
    bridge.update(weight=1/6,difficulty='middle',cluster='policy_bridge',exposed_bridge=True,
                  predicted_single_pass=[.2,.8],budget_seconds=600)
    # The former first-racer fault is a different treatment in a race. It is not
    # part of this primary comparison; use separate labelled failure scenarios.
    bridge['scenario']['fail_first_work']=False
    return [transcript(),ingest(),bridge,jobs(),temporal(),restore()]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--validate',action='store_true')
    ap.add_argument('--out',type=Path);a=ap.parse_args();ps=catalog()
    if a.validate: print(json.dumps(validate_projects(ps),indent=2))
    if a.out:
        if a.out.exists():raise FileExistsError('refuse to overwrite fixture export')
        a.out.mkdir(parents=True)
        for p in ps:
            write_tree(a.out/p['id']/'repo',p['repo'])
            for i,s in enumerate(p['stages'],1):
                write_tree(a.out/p['id']/f'stage-{i}'/'hidden',s['hidden_tests'])
                write_tree(a.out/p['id']/f'stage-{i}'/'reference',s['reference'])
        atomic(a.out/'catalog.json',ps)
    print(json.dumps({'catalog_sha256':digest(ps),'projects':len(ps),'stages':sum(len(p['stages']) for p in ps),
      'ultra':[p['id'] for p in ps if p['difficulty']=='ultra'],'difficulty_is_prediction':True},indent=2))

if __name__=='__main__':main()
