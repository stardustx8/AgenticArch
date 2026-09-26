"""Describe a project round without turning missing trials or reviews into passes."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.ho02_projects import catalog
from tools.ho02_support import digest, validate_review, pending_calls, DIMENSIONS, CRITICAL


def report(plan, root):
    projects={p['id']:p for p in catalog()}
    if digest(list(projects.values()))!=plan['catalog_sha256']: raise ValueError('use the pinned project catalog')
    families={};rows=[]
    for trial in plan['trials']:
        path=Path(root)/trial['id']; result=path/'result.json'; project=projects[trial['project']]
        row=dict(trial,first=None,final=None,reviewed_stages=0,critical_findings=0,
                 protected_violations=0,owner_answers=0,provider_calls=0,simulated_calls=0,unknown_call_usage=0,
                 dimensions={k:None for k in DIMENSIONS},critical_by_type={k:0 for k in CRITICAL},
                 usage_by_lane={},worker_seconds=0,recorded_wall_seconds=0,unknown_wall_segments=0,review_coverage=False)
        if result.exists():
            r=json.loads(result.read_text()); manifest=json.loads((path/'manifest.json').read_text())
            if (r['project']!=trial['project'] or r['policy']!=trial['policy'] or
                manifest['source_fingerprint']!=plan['source_fingerprint'] or manifest['mode']!=plan['mode']):
                raise ValueError('trial identity mismatch')
            stages=r['stages']; n=len(project['stages']); reviews=[]
            def correct(s,key):
                x=s.get(key)
                return bool(x and x['hidden_pass'] and x['all_tests_pass'] and x['protected_preserved'])
            row['first']=sum(correct(s,'first') for s in stages)/n
            row['final']=sum(s['correct_delivery'] for s in stages)/n
            row['protected_violations']=sum(s.get('final') is not None and not s['final']['protected_preserved'] for s in stages)
            for stage in stages:
                review_file=path/f'review-stage-{stage["stage"]}.json'
                if review_file.exists() and stage['final']:
                    review=validate_review(json.loads(review_file.read_text()),stage['final']['sha'])
                    row['reviewed_stages']+=1; reviews.append(review)
                    for key in CRITICAL: row['critical_by_type'][key]+=review['critical'][key]['value']
                    row['critical_findings']+=sum(item['value'] for item in review['critical'].values())
            row['review_coverage']=row['reviewed_stages']==n
            if row['review_coverage']:
                row['dimensions']={k:sum(r['dimensions'][k]['value'] for r in reviews)/n for k in DIMENSIONS}
        log=path/'events.jsonl'
        if log.exists():
            calls={}; start=None
            for line in log.read_text().splitlines():
                e=json.loads(line)
                if e['kind']=='owner_answer':row['owner_answers']+=1
                if e['kind']=='attempt_start':
                    if start is not None: row['unknown_wall_segments']+=1
                    start=e['ts']
                if e['kind']=='attempt_end' and start is not None:
                    row['recorded_wall_seconds']+=e['ts']-start;start=None
                if e['kind']=='call_start':
                    row['simulated_calls' if e.get('simulated') else 'provider_calls']+=1
                    calls[e['call_id']]=e['lane']
                if e['kind']=='call_end' and not e.get('simulated'):
                    row['worker_seconds']+=e.get('seconds',0)
                    if e.get('usage') is None:row['unknown_call_usage']+=1
                    else:
                        lane=calls.get(e['call_id'],'unknown')
                        totals=row['usage_by_lane'].setdefault(lane,{})
                        for key,value in e['usage'].items():
                            if type(value) in (int,float): totals[key]=totals.get(key,0)+value
            row['unknown_call_usage']+=len(pending_calls(log))
            row['unknown_wall_segments']+=start is not None
        rows.append(row)
    for arm in ('minimal','full'):
        values={}
        for ident,p in projects.items():
            selected=[r for r in rows if r['project']==ident and r['policy']==arm]
            if len(selected)!=plan['repeats']:raise ValueError('missing or duplicate planned identities')
            values[ident]={'weight':p['weight'],'planned':len(selected),'observed':sum(r['final'] is not None for r in selected)}
            values[ident]['rubric_0_to_4_bounds']={}
            for key in DIMENSIONS:
                known=[r['dimensions'][key] for r in selected if r['dimensions'][key] is not None]
                values[ident]['rubric_0_to_4_bounds'][key]=[sum(known)/len(selected),(sum(known)+4*(len(selected)-len(known)))/len(selected)]
            for key in ('first','final'):
                known=[r[key] for r in selected if r[key] is not None]
                values[ident][key+'_bounds']=[sum(known)/len(selected),(sum(known)+len(selected)-len(known))/len(selected)]
        families[arm]={'projects':values,'first_bounds':[sum(v['weight']*v['first_bounds'][i] for v in values.values()) for i in (0,1)],
            'final_bounds':[sum(v['weight']*v['final_bounds'][i] for v in values.values()) for i in (0,1)],
            'rubric_0_to_4_bounds':{k:[sum(v['weight']*v['rubric_0_to_4_bounds'][k][i] for v in values.values()) for i in (0,1)] for k in DIMENSIONS},
            'critical_by_type':{k:sum(r['critical_by_type'][k] for r in rows if r['policy']==arm) for k in CRITICAL}}
    return {'schema_version':1,'arms':families,'rows':rows,'all_reviews_complete':all(r['review_coverage'] for r in rows),
        'promotion':False,'uncertainty':'Bounds reflect missing planned trajectories, not sampling confidence. Six synthetic projects, one per family, cannot establish production noninferiority.',
        'critical_policy':'Do not average critical findings away. Missing reviews mean unknown, not zero events.',
        'cost_policy':'Inspect all append-only dispatch/call attempts, including interrupted ones. List-price and token fields are vendor proxies, not quota.'}

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',type=Path,required=True);ap.add_argument('--runs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.write_text(json.dumps(report(json.loads(a.plan.read_text()),a.runs),indent=2)+'\n')
