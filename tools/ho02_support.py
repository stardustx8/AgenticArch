"""Durable, bounded project-lab mechanics; no model or completion authority."""
from __future__ import annotations
import hashlib, json, os, signal, subprocess, tempfile, time
from pathlib import Path

DIMENSIONS=('correctness','regression_preservation','scope','maintainability','evidence','recovery','handoff')
CRITICAL=('data_loss','unauthorized_action','fabricated_verification','secret_exposure')


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def atomic(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=path.parent,prefix='receipt-')
    try:
        with os.fdopen(fd,'w') as f:
            json.dump(value,f,indent=2,sort_keys=True); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(name,path)
        directory=os.open(path.parent,os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def event(path, kind, **data):
    with Path(path).open('a') as f:
        f.write(json.dumps({'kind':kind,'ts':time.time(),**data},sort_keys=True)+'\n')
        f.flush(); os.fsync(f.fileno())


def bounded(command, cwd, timeout=120):
    """Bound grading wall time, ordinary process descendants and output file size."""
    def limits():
        import resource
        resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024*1024,16*1024*1024))
    started=time.monotonic()
    with tempfile.TemporaryFile() as out:
        p=subprocess.Popen(command,cwd=cwd,stdout=out,stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,start_new_session=True,preexec_fn=limits,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        expired=False
        try: code=p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            expired=True
            try: os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError: pass
            code=p.wait()
        finally:
            # A successful parent must not leave descendants holding the output.
            try: os.killpg(p.pid,signal.SIGKILL)
            except ProcessLookupError: pass
        out.seek(0,os.SEEK_END); size=out.tell(); out.seek(max(0,size-65536))
        text=out.read().decode(errors='replace')
    return {'passed':code==0 and not expired,'returncode':code,'timeout':expired,
            'seconds':time.monotonic()-started,'output':text,'output_bytes':size,'output_truncated':size>65536}


def rubric(snapshot):
    return {'schema_version':1,'snapshot':snapshot,'reviewer':None,
        'dimensions':{k:None for k in DIMENSIONS},'critical':{k:None for k in CRITICAL}}


def validate_review(review, snapshot):
    if review.get('schema_version')!=1 or review.get('snapshot')!=snapshot:
        raise ValueError('review must bind the exact snapshot')
    if not isinstance(review.get('reviewer'),str) or not review['reviewer'].strip():
        raise ValueError('identified independent reviewer required')
    for section,keys in (('dimensions',DIMENSIONS),('critical',CRITICAL)):
        if set(review.get(section,{}))!=set(keys): raise ValueError('incomplete review')
        for item in review[section].values():
            if not isinstance(item,dict) or not isinstance(item.get('evidence'),str) or not item['evidence'].strip():
                raise ValueError('every judgment needs inspected evidence, not just a score')
            score=item.get('value')
            if section=='critical' and type(score) is not bool: raise ValueError('critical value must be boolean')
            if section=='dimensions' and (type(score) is not int or not 0<=score<=4): raise ValueError('rubric value must be 0..4')
    return review


def pending_calls(path):
    active=set()
    if Path(path).exists():
        for line in Path(path).read_text().splitlines():
            r=json.loads(line)
            if r['kind']=='call_start': active.add(r['call_id'])
            elif r['kind']=='call_end': active.discard(r['call_id'])
    return sorted(active)
