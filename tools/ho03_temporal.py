"""Upper-edge event-time/knowledge-time reporting with synthetic business data."""
from tools.ho02_projects import project

SCHEMA='''
CREATE TABLE IF NOT EXISTS events(tenant TEXT,entity TEXT,revision INTEGER,valid_at INTEGER,
 recorded_at INTEGER,amount TEXT,currency TEXT,void INTEGER,PRIMARY KEY(tenant,entity,revision));
CREATE TABLE IF NOT EXISTS legacy_notes(id INTEGER PRIMARY KEY,note TEXT);
'''
QUERY='''
WITH visible AS (
 SELECT *,ROW_NUMBER() OVER(PARTITION BY entity ORDER BY revision DESC) AS n
 FROM events WHERE tenant=? AND recorded_at<=?
)
SELECT tenant,entity,revision,valid_at,recorded_at,amount,currency,void
FROM visible WHERE n=1 AND valid_at<=? AND void=0 ORDER BY entity;
'''
BASE='''
import sqlite3
from pathlib import Path
from decimal import Decimal
class Ledger:
 def __init__(self,path):
  self.db=sqlite3.connect(path);self.db.row_factory=sqlite3.Row
  self.db.executescript(Path(__file__).with_name('schema.sql').read_text())
 def close(self):self.db.close()
 def ingest(self,rows):
  for r in rows:self.db.execute('INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?,?)',tuple(r[k] for k in ('tenant','entity','revision','valid_at','recorded_at','amount','currency','void')))
  self.db.commit()
 def asof(self,tenant,valid,known):
  return [dict(r) for r in self.db.execute('SELECT * FROM events WHERE tenant=? AND valid_at<=? AND recorded_at<=? AND void=0 ORDER BY entity',(tenant,valid,known))]
 def totals(self,tenant,valid,known):
  out={}
  for r in self.asof(tenant,valid,known):out[r['currency']]=out.get(r['currency'],Decimal(0))+Decimal(r['amount'])
  return out
 def memberships(self,rows):pass
 def report(self,tenant,valid,known,rates):return {}
 def apply_batch(self,batch,events,memberships):self.ingest(events)
'''
REFERENCE='''
import sqlite3,json,hashlib
from pathlib import Path
from decimal import Decimal,InvalidOperation,ROUND_HALF_EVEN
from contextlib import contextmanager
EVENT_FIELDS=('tenant','entity','revision','valid_at','recorded_at','amount','currency','void')

def decimal(value):
 if not isinstance(value,str):raise ValueError('decimal text required')
 try:d=Decimal(value)
 except InvalidOperation:raise ValueError('invalid decimal') from None
 if not d.is_finite():raise ValueError('finite value required')
 return d

def event_row(r):
 if set(r)!=set(EVENT_FIELDS):raise ValueError('event fields')
 if any(not isinstance(r[k],str) or not r[k] for k in ('tenant','entity','currency')):raise ValueError('identity')
 if type(r['revision']) is not int or r['revision']<1:raise ValueError('revision')
 if any(type(r[k]) is not int for k in ('valid_at','recorded_at')):raise ValueError('time')
 if type(r['void']) is not bool:raise ValueError('void')
 decimal(r['amount']);return tuple(r[k] for k in EVENT_FIELDS)

class Ledger:
 def __init__(self,path):
  self.db=sqlite3.connect(path,isolation_level=None);self.db.row_factory=sqlite3.Row
  self.db.executescript(Path(__file__).with_name('schema.sql').read_text());self.upgrade()
 def upgrade(self):pass
 def close(self):self.db.close()
 @contextmanager
 def tx(self):
  self.db.execute('BEGIN IMMEDIATE')
  try:yield
  except BaseException:self.db.rollback();raise
  else:self.db.commit()
 def insert_events(self,rows):
  for r in rows:
   old=self.db.execute('SELECT * FROM events WHERE tenant=? AND entity=? AND revision=?',r[:3]).fetchone()
   if old:
    if tuple(old)!=r:raise ValueError('conflicting immutable event')
   else:self.db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)',r)
 def ingest(self,rows):
  values=[event_row(r) for r in rows]
  with self.tx():self.insert_events(values)
 def asof(self,tenant,valid,known):
  sql=Path(__file__).with_name('asof.sql').read_text()
  return [dict(r) for r in self.db.execute(sql,(tenant,known,valid))]
 def totals(self,tenant,valid,known):
  out={}
  for r in self.asof(tenant,valid,known):out[r['currency']]=out.get(r['currency'],Decimal(0))+Decimal(r['amount'])
  return out
 def memberships(self,rows):pass
 def report(self,tenant,valid,known,rates):return {}
 def apply_batch(self,batch,events,memberships):self.ingest(events)
'''
UPGRADE='''
 def upgrade(self):
  self.db.executescript("CREATE TABLE IF NOT EXISTS memberships(tenant TEXT,entity TEXT,start INTEGER,stop INTEGER,known INTEGER,team TEXT,PRIMARY KEY(tenant,entity,start,known)); CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY,digest TEXT);")
 def member_values(self,rows):
  keys=('tenant','entity','start','stop','known','team');out=[]
  for r in rows:
   if set(r)!=set(keys) or any(not isinstance(r[k],str) or not r[k] for k in ('tenant','entity','team')):raise ValueError('member fields')
   if type(r['start']) is not int or type(r['known']) is not int or (r['stop'] is not None and (type(r['stop']) is not int or r['stop']<=r['start'])):raise ValueError('member interval')
   out.append(tuple(r[k] for k in keys))
  return out
 def insert_members(self,rows):
  for r in rows:
   old=self.db.execute('SELECT * FROM memberships WHERE tenant=? AND entity=? AND start=? AND known=?',(r[0],r[1],r[2],r[4])).fetchone()
   if old:
    if tuple(old)!=r:raise ValueError('conflicting membership')
   else:self.db.execute('INSERT INTO memberships VALUES(?,?,?,?,?,?)',r)
 def memberships(self,rows):
  values=self.member_values(rows)
  with self.tx():self.insert_members(values)
 def report(self,tenant,valid,known,rates):
  members={}
  for r in self.db.execute('SELECT * FROM memberships WHERE tenant=? AND known<=? ORDER BY known',(tenant,known)):
   members[(r['entity'],r['start'])]=dict(r)
  current={}
  for r in members.values():
   if r['start']<=valid and (r['stop'] is None or valid<r['stop']):
    if r['entity'] in current:raise ValueError('overlapping active memberships')
    current[r['entity']]=r['team']
  out={}
  for r in self.asof(tenant,valid,known):
   rate=decimal(rates[r['currency']])
   if rate<=0:raise ValueError('nonpositive rate')
   value=int((Decimal(r['amount'])*rate*100).quantize(Decimal('1'),rounding=ROUND_HALF_EVEN))
   team=current.get(r['entity'],'unassigned');out[team]=out.get(team,0)+value
  return dict(sorted(out.items()))
 def apply_batch(self,batch,events,memberships):
  if not isinstance(batch,str) or not batch:raise ValueError('batch identity')
  ev=[event_row(r) for r in events]; mem=self.member_values(memberships)
  digest=hashlib.sha256(json.dumps([events,memberships],sort_keys=True,separators=(',',':')).encode()).hexdigest()
  with self.tx():
   old=self.db.execute('SELECT digest FROM batches WHERE id=?',(batch,)).fetchone()
   if old:
    if old[0]!=digest:raise ValueError('batch conflict')
    return False
   self.insert_events(ev);self.insert_members(mem)
   self.db.execute('INSERT INTO batches VALUES(?,?)',(batch,digest));return True
'''
CONTRACT='''
Repair an existing multi-module incremental business reporting system. The contract is in
ledger.py, schema.sql, asof.sql and docs/temporal.md. Ledger.ingest receives dictionaries with
exact fields tenant/entity/currency (nonempty strings), revision (positive int), valid_at and
recorded_at (ints, not bools), amount (finite Decimal text), void (bool). Preserve input order
and content in stored immutable revisions; a repeated identical key (tenant,entity,revision)
is a no-op, a differing value is ValueError, and the WHOLE ingest batch rolls back. Validate
all rows before committing; accept out-of-order revision arrival. Never overwrite a revision.
asof(tenant,V,K) first removes records with recorded_at>K, then picks maximum revision per
entity, THEN removes the chosen revision if valid_at>V or void. Do not resurrect an earlier
revision when a correction moves an event into the future or voids it. Return dict rows sorted
by entity, with original fields (SQLite bool 0/1 allowed). totals groups Decimal amounts by
currency. Different tenants, missing values, empty batches, and reopen must remain correct.
Legacy unrelated tables and original fixtures are immutable. No network or deployment.
'''
STAGE2='''
Requirements change: keep all existing time semantics, add bitemporal team memberships and
atomic incremental batches. memberships(rows) accepts exact tenant/entity/team nonempty
strings, start and known integers, stop either None or an integer strictly greater than start.
Identity (tenant,entity,start,known) is immutable with identical replay allowed; the whole batch
is atomic on conflict. report(tenant,V,K,rates) first chooses latest known<=K for each
(entity,start), then filters start<=V<stop (None means unbounded). Multiple active membership
intervals for one entity are an error, not a multiplied join. Entities without a current
membership use team 'unassigned'. Report active events from asof as base-currency INTEGER cents
by team; for each event separately multiply Decimal amount by the positive finite Decimal-text
rate for its currency, multiply by 100 and ROUND_HALF_EVEN to an integer, then sum. Never round
the grouped total instead. Return sorted team keys. Missing/invalid rates fail explicitly.
apply_batch(batch_id,events,memberships) commits both inputs and an idempotency receipt atomically.
Same batch_id plus identical ordered inputs returns False with no changes; conflict raises
ValueError. A new committed batch returns True. Membership conflicts after valid events must
roll back the events and receipt. Reopen/migrate existing populated databases without data loss.
Update docs/recovery.md with repeat/recovery assumptions. Validate offline only.
'''
HIDDEN1='''
import tempfile,random
from pathlib import Path
from decimal import Decimal
from ledger import Ledger

def ev(entity='x',rev=1,valid=1,known=1,amount='1.00',tenant='a',void=False):
 return dict(tenant=tenant,entity=entity,revision=rev,valid_at=valid,recorded_at=known,amount=amount,currency='CHF',void=void)
class Contract(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'db';self.l=Ledger(self.path)
 def tearDown(self):self.l.close();self.tmp.cleanup()
 def test_no_revision_resurrection(self):
  self.l.ingest([ev(),ev(rev=2,valid=50,known=3),ev('other',tenant='b')])
  self.assertEqual(len(self.l.asof('a',5,2)),1);self.assertEqual(self.l.asof('a',5,3),[])
  self.l.ingest([ev(rev=3,valid=1,known=4,void=True)])
  self.assertEqual(self.l.asof('a',100,4),[])
 def test_batch_rollback_on_conflict(self):
  self.l.ingest([ev()]);self.l.ingest([ev()])
  with self.assertRaises(ValueError):self.l.ingest([ev('new'),ev(amount='2.00')])
  self.assertEqual([r['entity'] for r in self.l.asof('a',5,5)],['x'])
  self.l.close();self.l=Ledger(self.path);self.assertEqual(self.l.totals('a',5,5),{'CHF':Decimal('1')})
 def test_invalid_late_row_preserves_good_data(self):
  self.l.ingest([ev()]);bad=ev('bad',amount='NaN')
  with self.assertRaises((ValueError,TypeError)):self.l.ingest([ev('new'),bad])
  self.assertEqual(len(self.l.asof('a',10,10)),1)
 def test_seeded_independent_relational_oracle(self):
  rng=random.Random(4813);rows=[]
  for name in range(16):
   for rev in range(1,5):rows.append(ev(str(name),rev,rng.randrange(20),rng.randrange(20),str(name+rev),void=rng.random()<.15))
  rng.shuffle(rows);self.l.ingest(rows)
  for valid in (0,4,9,19):
   for known in (0,5,11,19):
    latest={}
    for r in rows:
     if r['recorded_at']<=known and (r['entity'] not in latest or r['revision']>latest[r['entity']]['revision']):latest[r['entity']]=r
    expected=sorted(r['entity'] for r in latest.values() if r['valid_at']<=valid and not r['void'])
    self.assertEqual([r['entity'] for r in self.l.asof('a',valid,known)],expected)
'''
HIDDEN2=HIDDEN1+'''
def member(entity='x',start=0,stop=None,known=1,team='T',tenant='a'):
 return dict(tenant=tenant,entity=entity,start=start,stop=stop,known=known,team=team)
class RevisionContract(Contract):
 def test_half_open_membership_and_no_resurrection(self):
  self.l.ingest([ev()]);self.l.memberships([member(),member(stop=4,known=2)])
  self.assertEqual(self.l.report('a',5,1,{'CHF':'1'}),{'T':100})
  self.assertEqual(self.l.report('a',5,2,{'CHF':'1'}),{'unassigned':100})
 def test_overlap_is_not_join_multiplication(self):
  self.l.ingest([ev()]);self.l.memberships([member(),member(start=2,team='U')])
  with self.assertRaises(ValueError):self.l.report('a',3,3,{'CHF':'1'})
 def test_per_row_rounding(self):
  self.l.ingest([ev('x',amount='.005'),ev('y',amount='.005'),ev('z',amount='-.015')])
  self.assertEqual(self.l.report('a',2,2,{'CHF':'1'}),{'unassigned':-2})
 def test_cross_table_atomic_replay_after_restart(self):
  self.l.memberships([member()])
  with self.assertRaises(ValueError):self.l.apply_batch('batch',[ev('new')],[member(team='different')])
  self.assertEqual(self.l.asof('a',2,2),[])
  self.assertTrue(self.l.apply_batch('batch',[ev()],[member()]))
  self.l.close();self.l=Ledger(self.path)
  self.assertFalse(self.l.apply_batch('batch',[ev()],[member()]))
  with self.assertRaises(ValueError):self.l.apply_batch('batch',[ev('other')],[])
  self.assertEqual(len(self.l.asof('a',2,2)),1)
 def test_preserve_unrelated_schema(self):
  self.l.db.execute("INSERT INTO legacy_notes VALUES(7,'do not erase')");self.l.db.commit()
  self.l.apply_batch('batch',[ev()],[]);self.l.close();self.l=Ledger(self.path)
  self.assertEqual(self.l.db.execute('SELECT note FROM legacy_notes WHERE id=7').fetchone()[0],'do not erase')
'''

def build():
 p=project('u03_temporal','ai_data',1/6,['Python','SQLite','SQL','JSON'],{
  'ledger.py':BASE,'schema.sql':SCHEMA,'asof.sql':'SELECT * FROM events WHERE tenant=? AND valid_at<=? AND recorded_at<=?;\n',
  'service.py':'from ledger import Ledger\ndef open_ledger(path):return Ledger(path)\n',
  'reporting.py':'def report(ledger,tenant,valid,known,rates):return ledger.report(tenant,valid,known,rates)\n',
  'pipeline.py':'def apply(ledger,batch,events,members):return ledger.apply_batch(batch,events,members)\n',
  'cli.py':'import json,sys\nfrom service import open_ledger\nif __name__=="__main__":\n l=open_ledger(sys.argv[1]);l.ingest(json.load(sys.stdin));l.close()\n',
  'docs/temporal.md':CONTRACT,'docs/recovery.md':'Reopen the existing database; never replace original input files.\n',
  'config.toml':'[report]\nbase_currency = "CHF"\n'},
  '''
  import tempfile
  from pathlib import Path
  from service import open_ledger
  class Legacy(unittest.TestCase):
   def test_empty(self):
    with tempfile.TemporaryDirectory() as t:
     l=open_ledger(Path(t)/'db');self.assertEqual(l.asof('a',0,0),[]);l.close()
  ''',[CONTRACT,STAGE2],[{'ledger.py':REFERENCE,'asof.sql':QUERY},{'ledger.py':REFERENCE+UPGRADE}], [HIDDEN1,HIDDEN2],restart_after_first=True)
 p.update(difficulty='ultra',cluster='temporal_reporting',predicted_single_pass=[.05,.35],budget_seconds=1200)
 return p
