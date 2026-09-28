"""Upper-edge restore planning and journal recovery on real temporary files."""
from tools.ho02_projects import project

BASE='''
from pathlib import Path
import hashlib,json
class Conflict(RuntimeError):pass
class RecoveryRequired(RuntimeError):pass
def sha(data):return hashlib.sha256(data).hexdigest()
def build_plan(root,spec):
 root=Path(root).resolve()
 return {'version':1,'root':str(root),'entries':[dict(x,before=None,after=None) for x in spec]}
class Executor:
 def __init__(self,root,journal):self.root=Path(root);self.journal=Path(journal)
 def apply(self,plan,crash_after=None):
  for row in plan['entries']:
   p=self.root/row['path']
   if row['content'] is None:p.unlink(missing_ok=True)
   else:p.write_text(row['content'])
  return True
 def recover(self):return False
'''
PLAN='''
from pathlib import Path
import hashlib,json,os,stat,tempfile,base64
class Conflict(RuntimeError):pass
class RecoveryRequired(RuntimeError):pass
class SimulatedCrash(BaseException):pass

def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def root_path(root):
 p=Path(root)
 if p.is_symlink() or not p.is_dir():raise ValueError('root must be a real directory')
 return p.resolve()
def target(root,name):
 if not isinstance(name,str) or not name or '\\x00' in name or '\\\\' in name:raise ValueError('path')
 parts=name.split('/')
 if any(x in ('','.','..') for x in parts):raise ValueError('noncanonical relative path')
 p=root
 for part in parts[:-1]:
  p=p/part
  if p.is_symlink() or not p.is_dir():raise ValueError('parent is not an existing ordinary directory')
 p=p/parts[-1]
 if p.is_symlink() or (p.exists() and not p.is_file()):raise ValueError('nonregular target')
 return p

def state(p):return p.read_bytes() if p.exists() else None
def hash_state(value):return sha(value) if value is not None else None

def build_plan(root,spec):
 root=root_path(root)
 if not isinstance(spec,list):raise ValueError('list required')
 entries=[];seen=set()
 for row in spec:
  if not isinstance(row,dict) or set(row)!={'path','content'}:raise ValueError('entry fields')
  name=row['path'];p=target(root,name)
  if name in seen:raise ValueError('duplicate target')
  seen.add(name);content=row['content']
  if content is not None and not isinstance(content,str):raise ValueError('UTF-8 text required')
  new=content.encode('utf-8') if content is not None else None
  entries.append({'path':name,'content':content,'before':hash_state(state(p)),'after':hash_state(new)})
 return {'version':1,'root':str(root),'entries':sorted(entries,key=lambda r:r['path'])}

class Executor:
 def __init__(self,root,journal):self.root=root_path(root);self.journal=Path(journal)
 def apply(self,plan,crash_after=None):raise NotImplementedError('stage 2')
 def recover(self):return False
'''
EXEC='''
def durable_json(path,obj):
 data=canonical(obj)
 fd,name=tempfile.mkstemp(prefix='.restore-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(name,path);sync_dir(path.parent)
 finally:
  if os.path.exists(name):os.unlink(name)

def sync_dir(path):
 fd=os.open(path,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)

def replace_bytes(path,data):
 if data is None:
  path.unlink(missing_ok=True);sync_dir(path.parent);return
 fd,name=tempfile.mkstemp(prefix='.restore-',dir=path.parent)
 try:
  with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
  os.replace(name,path);sync_dir(path.parent)
 finally:
  if os.path.exists(name):os.unlink(name)

class Executor:
 def __init__(self,root,journal):
  self.root=root_path(root);self.journal=Path(journal).absolute()
  if self.journal.is_symlink() or not self.journal.parent.is_dir() or self.journal.parent.resolve().is_relative_to(self.root):raise ValueError('journal must be outside restore root')
 def checked_plan(self,plan):
  if not isinstance(plan,dict) or set(plan)!={'version','root','entries'} or type(plan['version']) is not int or plan['version']!=1 or plan['root']!=str(self.root):raise ValueError('plan identity')
  if not isinstance(plan['entries'],list):raise ValueError('entries')
  names=[]
  for r in plan['entries']:
   if not isinstance(r,dict) or set(r)!={'path','content','before','after'}:raise ValueError('plan fields')
   target(self.root,r['path']);names.append(r['path'])
   if r['content'] is not None and not isinstance(r['content'],str):raise ValueError('content')
   for key in ('before','after'):
    v=r[key]
    if v is not None and (not isinstance(v,str) or len(v)!=64 or any(c not in '0123456789abcdef' for c in v)):raise ValueError('hash')
   if hash_state(None if r['content'] is None else r['content'].encode())!=r['after']:raise ValueError('content digest')
  if names!=sorted(set(names)):raise ValueError('plan order or duplicate')
  return sha(canonical(plan))
 def read(self):
  if self.journal.is_symlink():raise ValueError('journal symlink')
  obj=json.loads(self.journal.read_text())
  if set(obj)!={'version','state','plan','digest','originals'} or obj['version']!=1 or obj['state'] not in ('prepared','committed','rolled_back'):raise ValueError('journal shape')
  if self.checked_plan(obj['plan'])!=obj['digest']:raise ValueError('journal digest')
  if len(obj['originals'])!=len(obj['plan']['entries']):raise ValueError('journal originals')
  for row,value in zip(obj['plan']['entries'],obj['originals']):
   data=base64.b64decode(value,validate=True) if value is not None else None
   if hash_state(data)!=row['before']:raise ValueError('corrupt original bytes')
  return obj
 def apply(self,plan,crash_after=None):
  ident=self.checked_plan(plan)
  if crash_after is not None and (type(crash_after) is not int or crash_after<0):raise ValueError('checkpoint')
  if self.journal.exists():
   old=self.read()
   if old['state']=='prepared':raise RecoveryRequired('explicit rollback required')
   if old['state']=='committed':
    if old['digest']!=ident:raise Conflict('journal belongs to another committed plan')
    if any(hash_state(state(target(self.root,r['path'])))!=r['after'] for r in plan['entries']):raise Conflict('committed output changed externally')
    return False
  originals=[]
  for row in plan['entries']:
   old=state(target(self.root,row['path']))
   if hash_state(old)!=row['before']:raise Conflict('source drift before any mutation')
   originals.append(None if old is None else base64.b64encode(old).decode())
  obj={'version':1,'state':'prepared','plan':plan,'digest':ident,'originals':originals}
  durable_json(self.journal,obj)
  if crash_after==0:raise SimulatedCrash()
  for i,row in enumerate(plan['entries'],1):
   replace_bytes(target(self.root,row['path']),None if row['content'] is None else row['content'].encode())
   if crash_after==i:raise SimulatedCrash()
  obj['state']='committed';durable_json(self.journal,obj)
  if crash_after==len(plan['entries'])+1:raise SimulatedCrash()
  return True
 def recover(self):
  if not self.journal.exists():return False
  obj=self.read()
  if obj['state'] in ('committed','rolled_back'):return False
  # Check every target before restoring ANY original. Never erase an external edit.
  for row in obj['plan']['entries']:
   if hash_state(state(target(self.root,row['path']))) not in (row['before'],row['after']):raise Conflict('external edit during interruption')
  for row,value in zip(obj['plan']['entries'],obj['originals']):
   replace_bytes(target(self.root,row['path']),None if value is None else base64.b64decode(value,validate=True))
  obj['state']='rolled_back';durable_json(self.journal,obj);return True
'''
CONTRACT='''
Repair this existing backup-restore preparation tool. Phase one must never mutate files.
build_plan(root,spec) accepts a real existing directory and a list of exact {path,content}
objects. content is UTF-8 text or None for an explicit deletion. Paths are canonical relative
POSIX names: no empty components, '.', '..', absolute paths, backslashes or NUL. Reject
symlink roots, symlink ancestors/targets, nonregular targets, missing parent directories and
duplicate paths. Do not silently normalize invalid input. New files in existing directories
and missing deletion targets are allowed. Return exact keys version=1, root=canonical absolute
root, entries sorted by path. Each entry contains path,content,before,after; before and after
are SHA-256 hex of existing bytes/proposed UTF-8 bytes, or None for absence. Preserve arbitrary
binary originals while hashing. No timestamp-dependent or extra fields. Changing an input
list after the call cannot change the plan. Existing unrelated data and notes stay untouched.
Separate path checking, digest planning, CLI and documented recovery assumptions. No network.
'''
STAGE2='''
Add an explicit, single-operator journalled restore transaction without weakening phase one.
Executor(root,journal_path) uses a journal outside the restore root. apply(plan,crash_after=None)
validates exact plan shape/version/root, sorted unique paths, digest syntax and content hashes.
Revalidate safe paths and ALL before-hashes before ANY target is mutated. Drift raises Conflict.
Store originals and the complete plan durably BEFORE any target mutation; file replacement and
journal changes use atomic replace, file fsync and parent-directory fsync. Journal may contain
base64 originals. A fresh successful apply returns True; replay of an identical committed plan
returns False only if all committed outputs still match, otherwise Conflict. A different plan
with the same committed journal is Conflict. A prepared journal requires explicit recover()
and raises RecoveryRequired on apply, not an automatic overwrite or fresh transaction.
recover() rolls a prepared transaction back to its originals and returns True; no journal,
committed or already rolled-back journals return False. Before restoring any original, verify
EVERY target is currently either its before image or after image. An external edit raises
Conflict without changing any target. Original absent files must become absent again. Reuse a
rolled-back journal for a revalidated plan. Corrupt journals fail explicitly, never treated as
success. This is a local single-operator protocol, not protection from a hostile racing user.
For deterministic crash tests define SimulatedCrash(BaseException): crash_after=0 raises after
prepared journal persists, n in 1..entry_count raises after the nth sorted target write, and
entry_count+1 raises after committed journal persists. No automatic rollback when this fires.
Recreate the Executor and call recover() to test restart. Real power failure is not simulated.
Keep non-target files, binary originals and legacy behavior; document limits in docs/recovery.md.
'''
HIDDEN1='''
import tempfile,hashlib,json,os
from pathlib import Path
from restore import build_plan
class Contract(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name);self.root=self.base/'root';self.root.mkdir();(self.root/'sub').mkdir()
  (self.root/'a').write_bytes(b'old');(self.root/'keep').write_bytes(b'private original')
 def tearDown(self):self.tmp.cleanup()
 def test_exact_plan_and_no_mutation(self):
  spec=[{'path':'sub/new','content':'ö'},{'path':'a','content':None}];p=build_plan(self.root,spec);spec[0]['content']='changed'
  self.assertEqual(p,{'version':1,'root':str(self.root.resolve()),'entries':[
   {'path':'a','content':None,'before':hashlib.sha256(b'old').hexdigest(),'after':None},
   {'path':'sub/new','content':'ö','before':None,'after':hashlib.sha256('ö'.encode()).hexdigest()}]})
  self.assertEqual((self.root/'a').read_bytes(),b'old');self.assertFalse((self.root/'sub/new').exists())
 def test_paths_are_not_normalized(self):
  for name in ('../outside','/tmp/escape','sub/../a','sub//x','./a','sub\\\\x','a/','missing/file'):
   with self.subTest(name=name),self.assertRaises((ValueError,TypeError)):build_plan(self.root,[{'path':name,'content':'bad'}])
 def test_symlink_targets_and_ancestors(self):
  (self.base/'outside').write_text('safe');(self.root/'link').symlink_to(self.base/'outside');(self.root/'directory').symlink_to(self.base,target_is_directory=True)
  for name in ('link','directory/outside'):
   with self.assertRaises(ValueError):build_plan(self.root,[{'path':name,'content':'bad'}])
  self.assertEqual((self.base/'outside').read_text(),'safe')
 def test_duplicate_and_non_text_are_errors(self):
  with self.assertRaises(ValueError):build_plan(self.root,[{'path':'a','content':'x'},{'path':'a','content':None}])
  with self.assertRaises(ValueError):build_plan(self.root,[{'path':'a','content':1}])
'''
HIDDEN2=HIDDEN1+'''
from restore import Executor,Conflict,RecoveryRequired,SimulatedCrash
class RecoveryContract(Contract):
 def spec(self):return [{'path':'a','content':'new'},{'path':'sub/new','content':'created'},{'path':'sub/binary','content':None}]
 def setup_binary(self):(self.root/'sub/binary').write_bytes(bytes(range(256)))
 def test_every_precommit_crash_rolls_back_and_replay_is_idempotent(self):
  for n in range(4):
   with self.subTest(checkpoint=n):
    (self.root/'a').write_bytes(b'old');(self.root/'sub/new').unlink(missing_ok=True);self.setup_binary()
    journal=self.base/f'journal-{n}';p=build_plan(self.root,self.spec());ex=Executor(self.root,journal)
    with self.assertRaises(SimulatedCrash):ex.apply(p,crash_after=n)
    with self.assertRaises(RecoveryRequired):Executor(self.root,journal).apply(p)
    self.assertTrue(Executor(self.root,journal).recover());self.assertFalse(Executor(self.root,journal).recover())
    self.assertEqual((self.root/'a').read_bytes(),b'old');self.assertFalse((self.root/'sub/new').exists())
    self.assertEqual((self.root/'sub/binary').read_bytes(),bytes(range(256)))
    self.assertTrue(Executor(self.root,journal).apply(p));self.assertFalse(Executor(self.root,journal).apply(p))
    self.assertEqual((self.root/'keep').read_bytes(),b'private original')
 def test_committed_crash_does_not_roll_back(self):
  self.setup_binary();p=build_plan(self.root,self.spec());journal=self.base/'journal'
  with self.assertRaises(SimulatedCrash):Executor(self.root,journal).apply(p,crash_after=4)
  self.assertFalse(Executor(self.root,journal).recover());self.assertFalse(Executor(self.root,journal).apply(p))
  self.assertEqual((self.root/'a').read_text(),'new')
 def test_late_external_edit_prevents_all_rollback(self):
  self.setup_binary();p=build_plan(self.root,self.spec());journal=self.base/'journal'
  with self.assertRaises(SimulatedCrash):Executor(self.root,journal).apply(p,crash_after=3)
  (self.root/'sub/new').write_text('owner edit');before={str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
  with self.assertRaises(Conflict):Executor(self.root,journal).recover()
  self.assertEqual({str(p):p.read_bytes() for p in self.root.rglob('*') if p.is_file()},before)
 def test_plan_drift_prevents_first_mutation(self):
  self.setup_binary();p=build_plan(self.root,self.spec());(self.root/'sub/binary').write_text('owner edit')
  with self.assertRaises(Conflict):Executor(self.root,self.base/'j').apply(p)
  self.assertEqual((self.root/'a').read_bytes(),b'old');self.assertFalse((self.root/'sub/new').exists())
 def test_digest_and_journal_corruption_never_succeed(self):
  p=build_plan(self.root,[{'path':'a','content':'new'}]);p['entries'][0]['content']='forged'
  with self.assertRaises(ValueError):Executor(self.root,self.base/'j').apply(p)
  (self.base/'j').write_text('{broken')
  with self.assertRaises((ValueError,KeyError)):Executor(self.root,self.base/'j').recover()
 def test_symlink_substitution_after_planning(self):
  p=build_plan(self.root,[{'path':'a','content':'new'}]);(self.root/'a').unlink();(self.base/'outside').write_text('safe');(self.root/'a').symlink_to(self.base/'outside')
  with self.assertRaises(ValueError):Executor(self.root,self.base/'j').apply(p)
  self.assertEqual((self.base/'outside').read_text(),'safe')
'''

def build():
 p=project('u03_restore','infrastructure',1/6,['Python','Bash','JSON','filesystem'],{
  'restore.py':BASE,'planner.py':'from restore import build_plan\n',
  'recovery.py':'from restore import Executor\n',
  'cli.py':'import json,sys\nfrom planner import build_plan\nif __name__=="__main__":print(json.dumps(build_plan(sys.argv[1],json.load(sys.stdin)),sort_keys=True))\n',
  'scripts/plan.sh':'#!/bin/sh\nset -eu\nexec python3 cli.py "$@"\n',
  'schemas/manifest.json':'{"type":"array","description":"relative target and text or null deletion"}\n',
  'docs/contract.md':CONTRACT,'docs/recovery.md':'Planning is read-only. Execution is not yet implemented.\n',
  'config.toml':'[restore]\nauto_approve = false\n'},
  '''
  import tempfile
  from restore import build_plan
  class Legacy(unittest.TestCase):
   def test_empty_plan(self):
    with tempfile.TemporaryDirectory() as t:self.assertEqual(build_plan(t,[])['entries'],[])
  ''',[CONTRACT,STAGE2],[{'restore.py':PLAN},{'restore.py':PLAN+EXEC}], [HIDDEN1,HIDDEN2],restart_after_first=True)
 p.update(difficulty='ultra',cluster='transactional_restore',predicted_single_pass=[.05,.30],budget_seconds=1200)
 return p
