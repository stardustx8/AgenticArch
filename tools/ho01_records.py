"""Opt-in lab receipts and conservative decision-record replay (stdlib only)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def fingerprint(root: Path, prefixes=('aa', 'tools', 'eval/lab/tasks', 'config')) -> str:
    """Hash source bytes, excluding caches, results, .git and machine state."""
    h = hashlib.sha256()
    for prefix in prefixes:
        base = root / prefix
        files = [base] if base.is_file() else sorted(base.rglob('*')) if base.exists() else []
        for p in files:
            if p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts and p.suffix != '.pyc':
                rel = p.relative_to(root).as_posix().encode()
                data = p.read_bytes()
                h.update(len(rel).to_bytes(8,'big') + rel + len(data).to_bytes(8,'big') + data)
    return h.hexdigest()


def receipt(root: Path, task_dir: Path, flags: dict, config: dict) -> dict:
    try:
        sha = subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        sha = None
    normalized = {k:v for k,v in config.items() if k != 'paths'}
    encoded = lambda value: json.dumps(value,sort_keys=True,separators=(',',':'),default=str).encode()
    return {'schema_version':2, 'source_sha':sha, 'source_fingerprint':fingerprint(root),
            'task_fingerprint':fingerprint(task_dir,('task.json','repo','hidden','reference')),
            'flags_sha256':hashlib.sha256(encoded(flags)).hexdigest(),
            'effective_config_without_paths_sha256':hashlib.sha256(encoded(normalized)).hexdigest(),
            'python_version':sys.version.split()[0], 'config_paths_excluded':True}


def save_records(art: Path, db, calls: list[dict], state: Path, metadata: dict) -> None:
    """Save before hidden grading, so a grader crash does not erase worker evidence.

    Contains local paths/task records: keep real-task exports private. Call usage
    is cumulative provider output, not peak context or subscription headroom.
    """
    art.mkdir(parents=True,exist_ok=True)
    (art/'receipt.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (art/'calls.jsonl').write_text(''.join(json.dumps(c,default=str)+'\n' for c in calls))
    records=[dict(r) for r in db.q('SELECT * FROM decisions ORDER BY id')]
    (art/'decisions.jsonl').write_text(''.join(json.dumps(r,default=str)+'\n' for r in records))
    events=[]
    for p in sorted((state/'stop-hooks').rglob('events.jsonl')):
        for line in p.read_text().splitlines():
            try:
                events.append({'capsule':p.parent.name,'event':json.loads(line)})
            except ValueError:
                events.append({'capsule':p.parent.name,'event':{'status':'invalid_event'}})
    (art/'stop-events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))


def replay(records: list[dict]) -> list[dict]:
    """Audit the *recorded* menu. Missing live-state fields mean abstention.

    Historical final choice is retained as evidence, never supplied as a
    fallback. Historical outcome is excluded from selector inputs and replayed
    output. A proposed choice may be menu-valid without being the deployed pick.
    """
    out=[]
    for r in records:
        options=r.get('options',{})
        if isinstance(options,str):
            try: options=json.loads(options)
            except ValueError: options={}
        menu=set(options) if isinstance(options,dict) else set()
        proposed=r.get('proposed')
        out.append({'id':r.get('id'),'task_id':r.get('task_id'),'kind':r.get('kind'),
                    'recorded_final':r.get('final'), 'proposed_in_recorded_menu':proposed in menu if isinstance(proposed,str) else False,
                    'menu_size':len(menu),'source':'historical_menu_audit',
                    'counterfactual_outcome':None,'deployment_replay':'abstain_missing_live_state'})
    return out


def main():
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--decisions',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args()
    rs=[json.loads(line) for line in a.decisions.read_text().splitlines() if line.strip()]
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with a.out.open('x') as f:
        f.write(''.join(json.dumps(r)+'\n' for r in replay(rs)))

if __name__=='__main__':
    main()
