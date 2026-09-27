"""Upper-edge durable-job project. All data and service failures are synthetic."""
from tools.ho02_projects import project, clean

SCHEMA = '''
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY, tenant TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,
 state TEXT NOT NULL, owner TEXT, expires INTEGER, fence INTEGER NOT NULL DEFAULT 0,
 result TEXT, UNIQUE(tenant,key));
'''
BASE = '''
import json, sqlite3, uuid
from pathlib import Path
class Store:
 def __init__(self,path):
  self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row
  self.db.executescript(Path(__file__).with_name('schema.sql').read_text())
 def close(self): self.db.close()
 def submit(self,tenant,key,payload):
  ident=uuid.uuid4().hex
  self.db.execute('INSERT OR REPLACE INTO jobs(id,tenant,key,payload,state) VALUES(?,?,?,?,?)',
   (ident,tenant,key,json.dumps(payload),'ready'));self.db.commit();return ident
 def get(self,tenant,key):
  r=self.db.execute('SELECT * FROM jobs WHERE tenant=? AND key=?',(tenant,key)).fetchone()
  if r is None:return None
  d=dict(r);d['payload']=json.loads(d['payload']);d['result']=json.loads(d['result']) if d['result'] else None;return d
 def claim(self,worker,now,ttl):
  r=self.db.execute("SELECT * FROM jobs WHERE state='ready' ORDER BY rowid LIMIT 1").fetchone()
  if not r:return None
  self.db.execute("UPDATE jobs SET state='leased',owner=?,expires=?,fence=fence+1 WHERE id=?",(worker,now+ttl,r['id']));self.db.commit()
  return self.get(r['tenant'],r['key'])
 def complete(self,ident,worker,fence,result,now):
  self.db.execute("UPDATE jobs SET state='done',result=? WHERE id=?",(json.dumps(result),ident));self.db.commit();return True
 def cancel(self,tenant,key): return False
 def events(self,tenant,after=0): return []
'''
REFERENCE = '''
import json, sqlite3, uuid
from pathlib import Path
from contextlib import contextmanager

def encode(value):
 if not isinstance(value,dict): raise ValueError('object required')
 return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)

class Store:
 def __init__(self,path):
  self.db=sqlite3.connect(path,isolation_level=None,timeout=5);self.db.row_factory=sqlite3.Row
  self.db.executescript(Path(__file__).with_name('schema.sql').read_text())
  self.upgrade()
 def upgrade(self): pass
 def close(self): self.db.close()
 @contextmanager
 def tx(self):
  self.db.execute('BEGIN IMMEDIATE')
  try: yield
  except BaseException:
   self.db.rollback();raise
  else:self.db.commit()
 def emit(self,ident): pass
 def get(self,tenant,key):
  r=self.db.execute('SELECT * FROM jobs WHERE tenant=? AND key=?',(tenant,key)).fetchone()
  if r is None:return None
  d=dict(r);d['payload']=json.loads(d['payload']);d['result']=json.loads(d['result']) if d['result'] is not None else None;return d
 def submit(self,tenant,key,payload):
  if not isinstance(tenant,str) or not tenant or not isinstance(key,str) or not key:raise ValueError('identity required')
  value=encode(payload)
  with self.tx():
   old=self.db.execute('SELECT id,payload FROM jobs WHERE tenant=? AND key=?',(tenant,key)).fetchone()
   if old:
    if encode(json.loads(old['payload']))!=value:raise ValueError('idempotency conflict')
    return old['id']
   ident=uuid.uuid4().hex
   self.db.execute('INSERT INTO jobs(id,tenant,key,payload,state) VALUES(?,?,?,?,?)',(ident,tenant,key,value,'ready'))
   self.emit(ident);return ident
 def claim(self,worker,now,ttl):
  if not isinstance(worker,str) or not worker or type(now) is not int or type(ttl) is not int or ttl<=0:raise ValueError('lease arguments')
  with self.tx():
   r=self.db.execute("SELECT * FROM jobs WHERE state='ready' OR (state='leased' AND expires<=?) ORDER BY rowid LIMIT 1",(now,)).fetchone()
   if not r:return None
   self.db.execute("UPDATE jobs SET state='leased',owner=?,expires=?,fence=fence+1 WHERE id=?",(worker,now+ttl,r['id']))
   self.emit(r['id']);return self.get(r['tenant'],r['key'])
 def complete(self,ident,worker,fence,result,now):
  value=encode(result)
  if type(fence) is not int or type(now) is not int:return False
  with self.tx():
   changed=self.db.execute("UPDATE jobs SET state='done',result=? WHERE id=? AND state='leased' AND owner=? AND fence=? AND expires>?",(value,ident,worker,fence,now)).rowcount
   if changed:self.emit(ident)
   return bool(changed)
 def cancel(self,tenant,key): return False
 def events(self,tenant,after=0): return []
'''
UPGRADE = '''
 def upgrade(self):
  with self.tx():
   if 'revision' not in {r[1] for r in self.db.execute('PRAGMA table_info(jobs)')}:
    self.db.execute('ALTER TABLE jobs ADD COLUMN revision INTEGER NOT NULL DEFAULT 0')
   self.db.execute('CREATE TABLE IF NOT EXISTS events(tenant TEXT,seq INTEGER,body TEXT,PRIMARY KEY(tenant,seq))')
 def emit(self,ident):
  self.db.execute('UPDATE jobs SET revision=revision+1 WHERE id=?',(ident,))
  r=self.db.execute('SELECT * FROM jobs WHERE id=?',(ident,)).fetchone()
  seq=self.db.execute('SELECT COALESCE(MAX(seq),0)+1 FROM events WHERE tenant=?',(r['tenant'],)).fetchone()[0]
  body={'seq':seq,'job':ident,'version':r['revision'],'state':r['state'],'result':json.loads(r['result']) if r['result'] is not None else None}
  self.db.execute('INSERT INTO events VALUES(?,?,?)',(r['tenant'],seq,json.dumps(body)))
 def cancel(self,tenant,key):
  with self.tx():
   r=self.db.execute('SELECT * FROM jobs WHERE tenant=? AND key=?',(tenant,key)).fetchone()
   if not r or r['state'] in ('done','cancelled'):return False
   self.db.execute("UPDATE jobs SET state='cancelled',fence=fence+1 WHERE id=?",(r['id'],));self.emit(r['id']);return True
 def events(self,tenant,after=0):
  return [json.loads(r[0]) for r in self.db.execute('SELECT body FROM events WHERE tenant=? AND seq>? ORDER BY seq',(tenant,after))]
'''
REDUCER = '''
const {isDeepStrictEqual} = require('node:util');
function reduce(state, events) {
 const s=structuredClone(state);
 for (const e of events) {
  if (!Number.isSafeInteger(e.seq)||e.seq<=0||!Number.isSafeInteger(e.version)||e.version<=0||typeof e.job!=='string'||!e.job||!['ready','leased','done','cancelled'].includes(e.state)) throw Error('invalid event');
  if(e.seq<=s.cursor) continue;
  if(s.pending[e.seq]&&!isDeepStrictEqual(s.pending[e.seq],e)) throw Error('conflicting replay');
  s.pending[e.seq]=structuredClone(e);
 }
 while(s.pending[s.cursor+1]) {
  const e=s.pending[++s.cursor];delete s.pending[s.cursor];
  if(!s.jobs[e.job]||e.version>s.jobs[e.job].version) s.jobs[e.job]=structuredClone(e);
 }
 return s;
}
module.exports={reduce};
'''
CONTRACT = '''
Upgrade an existing SQLite-backed accepted-job service without changing get/submit signatures.
Read store.py, service.py, api.py, schema.sql, docs/contracts.md, and web/reducer.js.
Stage 1 contract: submit(tenant,key,payload) is idempotent for the same JSON object, independent
of object-key ordering. Reusing a tenant/key with a different payload raises ValueError and
preserves its old job, even after completion. Different tenants never share keys. Only
nonempty string identities and JSON objects containing finite JSON values are accepted.
claim(worker,now,ttl) leases the oldest inserted ready job or expired lease, with integer
now and positive integer ttl. The expiry is exclusive: now == expires is expired. Every
claim increments a monotonically increasing fencing token, also across close/reopen.
complete(id,worker,fence,result,now) commits only for the current live lease and owner/token;
stale, wrong-owner, expired or terminal completions return False and do not alter state.
All submit/claim/complete operations are SQLite transactions, safe across separate connections.
Stored input and returned values are detached; preserve unrelated records and schema data.
Failures must leave a reopenable database, not partial effects. No service/network deployment.
'''
STAGE2 = '''
The client must now reconnect without losing acknowledged state, and users must cancel jobs.
Keep stage 1 behavior and old populated databases. Migrate old schema by adding revision if
absent (starts at zero) and a persistent events table, without inventing historical events.
For every actual submit/claim/complete/cancel state change, atomically append a per-tenant
contiguous sequence event {seq,job,version,state,result}. Increment that job's revision each
transition. Idempotent retries and failed completions create no events. events(tenant,after)
returns only that tenant's events with seq > after in ascending order, surviving restart.
cancel(tenant,key) changes ready/leased to cancelled, invalidates the lease, returns True
only on the first transition, and leaves done/cancelled/absent jobs unchanged (False).
A cancelled key remains reserved: identical submit returns its old id, not a new job.
Implement web/reducer.js reduce(state,events) for state {cursor:0,jobs:{},pending:{}}.
It must not mutate either input; buffer sequence gaps; apply only contiguous sequences;
ignore already applied sequences; reject inconsistent duplicate buffered sequence records;
never replace a job with a lower/equal version. Validate event seq/version positive safe
integers, job nonempty string, and state in ready/leased/done/cancelled. Future out-of-order
records must survive JSON save/reload. Update CLI/docs coherently. No hidden-test feedback.
'''
HIDDEN1 = '''
import tempfile, math
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from store import Store
class Contract(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db';self.s=Store(self.path)
 def tearDown(self): self.s.close();self.tmp.cleanup()
 def test_replay_conflict_and_tenant_boundary(self):
  x={'nested':{'b':[2],'a':1}};a=self.s.submit('a','k',x);x['nested']['b'].append(3)
  self.assertEqual(a,self.s.submit('a','k',{'nested':{'a':1,'b':[2]}}))
  with self.assertRaises(ValueError):self.s.submit('a','k',{'nested':{'a':1,'b':[3]}})
  self.assertNotEqual(a,self.s.submit('b','k',{}));self.assertEqual(self.s.get('a','k')['payload']['nested']['b'],[2])
 def test_fencing_restart_and_expiry(self):
  a=self.s.submit('a','k',{});x=self.s.claim('old',0,10)
  self.assertFalse(self.s.complete(a,'old',x['fence'],{},10))
  self.s.close();self.s=Store(self.path);y=self.s.claim('new',10,10)
  self.assertGreater(y['fence'],x['fence']);self.assertFalse(self.s.complete(a,'old',x['fence'],{},11))
  self.assertFalse(self.s.complete(a,'wrong',y['fence'],{},11));self.assertTrue(self.s.complete(a,'new',y['fence'],{'x':1},11))
  self.assertFalse(self.s.complete(a,'new',y['fence'],{'x':2},12));self.assertEqual(self.s.get('a','k')['result'],{'x':1})
 def test_concurrent_submit_and_claim(self):
  def submit(_):
   s=Store(self.path)
   try:return s.submit('a','key',{'v':1})
   finally:s.close()
  with ThreadPoolExecutor(4) as ex:ids=list(ex.map(submit,range(12)))
  self.assertEqual(len(set(ids)),1)
  def claim(i):
   s=Store(self.path)
   try:return s.claim(str(i),0,10)
   finally:s.close()
  with ThreadPoolExecutor(4) as ex:claims=list(ex.map(claim,range(8)))
  self.assertEqual(sum(x is not None for x in claims),1)
 def test_invalid_payload_does_not_modify_store(self):
  for payload in ([],{'x':float('nan')},{'x':float('inf')}):
   with self.assertRaises((ValueError,TypeError)):self.s.submit('a','bad',payload)
  self.assertIsNone(self.s.get('a','bad'))
  self.s.submit('a','good',{});self.assertIsNotNone(self.s.claim('w',0,1))
 def test_repeated_lease_schedule(self):
  a=self.s.submit('a','k',{});old=[]
  for now in range(0,50,5):
   lease=self.s.claim('worker-'+str(now),now,5);self.assertIsNotNone(lease)
   for worker,token in old:self.assertFalse(self.s.complete(a,worker,token,{'bad':1},now))
   old.append((lease['owner'],lease['fence']))
  self.assertTrue(self.s.complete(a,old[-1][0],old[-1][1],{'ok':1},49))
'''
HIDDEN2 = HIDDEN1 + '''
import json, subprocess, sqlite3
class RevisionContract(Contract):
 def test_cancel_outbox_and_reopen(self):
  ident=self.s.submit('a','k',{});lease=self.s.claim('w',0,20)
  self.assertTrue(self.s.cancel('a','k'));self.assertFalse(self.s.cancel('a','k'))
  self.assertFalse(self.s.complete(ident,'w',lease['fence'],{},1));self.assertEqual(self.s.submit('a','k',{}),ident)
  self.s.submit('b','k',{})
  ev=self.s.events('a');self.assertEqual([e['seq'] for e in ev],[1,2,3]);self.assertEqual([e['state'] for e in ev],['ready','leased','cancelled'])
  self.assertEqual([e['version'] for e in ev],[1,2,3]);self.assertEqual(self.s.events('a',2),ev[2:])
  self.s.close();self.s=Store(self.path);self.assertEqual(self.s.events('a'),ev)
 def test_populated_legacy_migration(self):
  p=Path(self.tmp.name)/'legacy';db=sqlite3.connect(p)
  db.executescript(Path('schema.sql').read_text())
  db.execute("INSERT INTO jobs(id,tenant,key,payload,state) VALUES('old','a','legacy','{}','ready')");db.commit();db.close()
  s=Store(p)
  try:
   self.assertEqual(s.get('a','legacy')['id'],'old');self.assertEqual(s.events('a'),[])
   self.assertIsNotNone(s.claim('worker',1,2));self.assertEqual(s.events('a')[0]['version'],1)
  finally:s.close()
 def test_js_gap_buffer_immutable_and_stale_version(self):
  code="""
const assert=require('node:assert/strict');const {reduce}=require('./web/reducer.js');
const z={cursor:0,jobs:{},pending:{}};
const e=(seq,version,state)=>({seq,version,state,job:'j',result:null});
let a=reduce(z,[e(3,3,'done'),e(1,1,'ready')]);assert.equal(a.cursor,1);assert.equal(z.cursor,0);
a=JSON.parse(JSON.stringify(a));a=reduce(a,[e(2,2,'leased')]);assert.equal(a.cursor,3);assert.equal(a.jobs.j.state,'done');
a=reduce(a,[e(4,1,'ready'),e(2,2,'leased')]);assert.equal(a.cursor,4);assert.equal(a.jobs.j.state,'done');
assert.throws(()=>reduce(z,[e(2,1,'ready'),e(2,2,'done')]));
assert.throws(()=>reduce(z,[e(1,1,'unknown')]));
console.log('ok');
"""
  q=subprocess.run(['node','-e',code],capture_output=True,text=True,timeout=10);self.assertEqual(q.returncode,0,q.stderr)
 def test_outbox_failure_rolls_back_transition(self):
  a=self.s.submit('a','k',{});lease=self.s.claim('w',0,10)
  self.s.db.execute("CREATE TRIGGER fail_event BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'injected'); END")
  with self.assertRaises(sqlite3.DatabaseError):self.s.complete(a,'w',lease['fence'],{'x':1},1)
  self.assertEqual(self.s.get('a','k')['state'],'leased');self.assertEqual(len(self.s.events('a')),2)
'''

def build():
    ref2=REFERENCE+UPGRADE
    p=project('u03_jobs','existing_feature',1/6,['Python','SQLite','JavaScript','JSON'],{
        'store.py':BASE,'schema.sql':SCHEMA,
        'service.py':'from store import Store\ndef open_store(path): return Store(path)\n',
        'api.py':'def status(store,tenant,key):\n return store.get(tenant,key)\n',
        'web/reducer.js':'module.exports.reduce=(state,events)=>state;\n',
        'web/client.js':'const {reduce}=require("./reducer.js"); module.exports={reduce};\n',
        'docs/contracts.md':CONTRACT,'docs/legacy.md':'get returns None for an unknown tenant/key. SQLite data is durable.\n',
        'config.toml':'[service]\noffline = true\n',
        'cli.py':'import json,sys\nfrom service import open_store\nif __name__=="__main__":\n s=open_store(sys.argv[1]); print(json.dumps(s.get(sys.argv[2],sys.argv[3]))); s.close()\n'},
        '''
        import tempfile
        from pathlib import Path
        from service import open_store
        class Legacy(unittest.TestCase):
         def test_basic_persistence(self):
          with tempfile.TemporaryDirectory() as t:
           s=open_store(Path(t)/'db');a=s.submit('a','k',{'hello':1});self.assertEqual(s.get('a','k')['id'],a);self.assertIsNone(s.get('b','k'));s.close()
        ''',[CONTRACT,STAGE2],[{'store.py':REFERENCE},{'store.py':ref2,'web/reducer.js':REDUCER}],[HIDDEN1,HIDDEN2],restart_after_first=True)
    p.update(difficulty='ultra',cluster='durable_jobs',predicted_single_pass=[.05,.40],budget_seconds=1200)
    return p
