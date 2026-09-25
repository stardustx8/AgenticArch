from dataclasses import replace
import copy
import json
from pathlib import Path
import unittest
from reference.routing import (Boundary, Capability, Task, accept_effort, compile_effort,
    compile_route, eligible, lease_valid, quota_delta, resolve_route, validate_catalog)

ROOT = Path(__file__).resolve().parents[1]
CAT = json.loads((ROOT / 'config/model-routing.json').read_text())
P = dict(encoder_revision='encoder', tokenizer_revision='tokenizer', head_sha256='a'*64,
         pooling='last-token', runtime_revision='runtime', renderer_version='v1')


def caps():
    return {k: Capability(m['identity'], tuple(m['efforts']),
                'chatgpt_web_subscription' if k == 'pro' else
                'native_claude_code_subscription' if k in {'fable51','opus55'} else
                'native_codex_subscription', 100, True, True, True, True)
            for k,m in CAT['models'].items() if m['status'] == 'candidate'}


def task(complexity='medium_tough', **kw):
    return Task(complexity, 'Implement the approved job status view.', 'snapshot', 'requirements', assessed=True, **kw)


def choose(t=None, c=None, **kw):
    return eligible(CAT, t or task(), c or caps(), profile='codex', slot='worker', now=101, **kw)


def plan(c=None, t=None):
    return compile_route(CAT,t or task(),c or caps(),profile='codex',slot='worker',now=101,
        baseline='astra_high',clm_model='pinned',provenance=P,token_counter=lambda s:len(s.split()))


def reply(p, selected):
    keys=json.loads(p.request.body)['questions']['decision']['criteria']
    return {'model':'pinned','answers':{'decision':{'type':'choice','choice':selected,
            'probabilities':{k:1.0 if k==selected else 0.0 for k in keys}}}}


class RoutingTests(unittest.TestCase):
    def test_catalog(self): validate_catalog(CAT)

    def test_medium_peers(self): self.assertEqual(set(choose()),{'astra_high','opus_medium','opus_high'})

    def test_bounded_excludes_luna_low(self): self.assertNotIn('luna_low',choose(task('bounded')))

    def test_tough_and_architecture_do_not_use_worker(self):
        self.assertFalse(choose(task('tough')))
        self.assertFalse(choose(task('routine',categories=('architecture',))))

    def test_deep_partner_options_and_anchor(self):
        for slot, expected in [('anchor',{'pro_web'}),('reviewer',{'review_fable51','review_opus55'})]:
            self.assertEqual(set(eligible(CAT,task('tough'),caps(),profile='pi',slot=slot,now=101)),expected)

    def test_future_model_stays_pending(self):
        c=copy.deepcopy(CAT);c['models']['fable55']['status']='candidate'
        with self.assertRaises(ValueError):validate_catalog(c)

    def test_no_api_or_wrong_model_fallback(self):
        for field,value in [('transport','paid_api'),('identity','different-model'),('qualified',False),
                            ('subscribed',False),('permitted',False),('quota_available',False),
                            ('observed_at',-1000),('observed_at',200)]:
            c=caps();c['astra']=replace(c['astra'],**{field:value})
            with self.subTest(field=field):self.assertNotIn('astra_high',choose(c=c))

    def test_native_pi_does_not_accept_claude_token(self):
        c=caps();c['opus55']=replace(c['opus55'],transport='pi_claude_subscription')
        self.assertNotIn('opus_high',eligible(CAT,task(),c,profile='pi',slot='worker',now=101))

    def test_qualified_pi_openai_profile_only(self):
        c=caps();c['astra']=replace(c['astra'],transport='qualified_pi_openai_subscription')
        self.assertIn('astra_high',eligible(CAT,task(),c,profile='pi',slot='worker',now=101))
        self.assertNotIn('astra_high',choose(c=c))

    def test_unsupported_effort_excluded(self):
        c=caps();c['opus55']=replace(c['opus55'],efforts=('medium',))
        self.assertNotIn('opus_high',choose(c=c))

    def test_unknown_assessment(self):
        self.assertFalse(choose(t=replace(task(),assessed=False)))
        with self.assertRaises(ValueError):choose(task('not_known'))

    def test_clm_receives_descriptive_choices_not_registry(self):
        p=plan();body=json.loads(p.request.body)
        self.assertIn('insufficient',body['questions']['decision']['criteria'])
        self.assertNotIn('api_usd_per_attempt',p.request.body.decode())
        self.assertNotIn('sources',body)

    def test_shadow_retains_baseline(self):
        p=plan();self.assertEqual(resolve_route(p,reply(p,'opus_medium'),refreshed=plan()),'astra_high')

    def test_advisory_needs_qualification(self):
        p=plan()
        with self.assertRaises(ValueError):resolve_route(p,reply(p,'opus_medium'),refreshed=p,mode='advisory')
        self.assertEqual(resolve_route(p,reply(p,'opus_medium'),refreshed=p,mode='advisory',
            qualified_policy_digest=p.eligibility_digest),'opus_medium')

    def test_stale_or_abstained_decision(self):
        p=plan();new=plan(t=replace(task(),snapshot='new'))
        with self.assertRaises(ValueError):resolve_route(p,reply(p,'opus_medium'),refreshed=new)
        self.assertEqual(resolve_route(p,reply(p,'insufficient'),refreshed=p),'astra_high')

    def test_changed_eligibility_does_not_dispatch(self):
        p=plan();c=caps();c['opus55']=replace(c['opus55'],quota_available=False)
        with self.assertRaises(ValueError):resolve_route(p,reply(p,'opus_medium'),refreshed=plan(c))

    def test_illicit_menu_and_tier(self):
        c=copy.deepcopy(CAT);c['models']['luna']['efforts'].append('max')
        with self.assertRaises(ValueError):validate_catalog(c)
        c=copy.deepcopy(CAT);c['routes']['luna_low']['tier']=2
        with self.assertRaises(ValueError):validate_catalog(c)


class EffortTests(unittest.TestCase):
    def setUp(self):self.b=Boundary('session','luna',3,'revision')
    def lease(self,**kw):
        args=dict(effort='high',generations=2,minimum='low',effective_model='luna',
                  effective_effort='high',effective_generation=3,applied_receipt='observed-receipt')
        args.update(kw);return accept_effort(self.b,**args)

    def test_generation_lease_includes_next(self):
        l=self.lease();self.assertTrue(lease_valid(l,self.b))
        self.assertTrue(lease_valid(l,replace(self.b,generation=4)))
        self.assertFalse(lease_valid(l,replace(self.b,generation=5)))

    def test_invalidations(self):
        l=self.lease()
        for field,value in [('revision','new'),('model','astra'),('session_id','other'),
                            ('manual_override',True),('streaming',True),('generation',2)]:
            self.assertFalse(lease_valid(l,replace(self.b,**{field:value})))

    def test_clamp_and_missing_receipt(self):
        for arg in [dict(effective_effort='medium'),dict(effective_model='astra'),
                    dict(effective_generation=4),dict(applied_receipt='')]:
            with self.assertRaises(ValueError):self.lease(**arg)

    def test_disallowed_lease_effort_and_floor(self):
        for arg in [dict(effort='max'),dict(generations=True),dict(generations=3),
                    dict(effort='low',minimum='high',effective_effort='low')]:
            with self.assertRaises(ValueError):self.lease(**arg)

    def test_manual_override_prevents_request(self):
        self.b=replace(self.b,manual_override=True)
        with self.assertRaises(ValueError):self.lease()

    def test_single_effort_needs_no_model_call(self):
        args=dict(evidence='Inspect failure',clm_model='pinned',provenance=P,
                  token_counter=lambda s:len(s.split()))
        self.assertIsNone(compile_effort(CAT,replace(self.b,model='astra'),minimum='high',**args))
        p=compile_effort(CAT,self.b,minimum='low',**args)
        self.assertEqual(set(json.loads(p.body)['questions']['effort']['criteria']),{'low','high','insufficient'})


class QuotaTests(unittest.TestCase):
    def setUp(self):self.b=dict(pool='openai',window='short',reset_at=1000,plan='pro',
        measurement_protocol='isolated-dashboard-v1',isolated=True,used_fraction=.2)
    def test_comparable_delta(self):self.assertAlmostEqual(quota_delta(self.b,{**self.b,'used_fraction':.3}),.1)
    def test_unknown_reset_concurrent_and_crosspool(self):
        for k,v in [('used_fraction',None),('used_fraction',.1),('used_fraction',True),
                    ('isolated',False),('reset_at',2000),('pool','claude')]:
            self.assertIsNone(quota_delta(self.b,{**self.b,k:v}))


if __name__ == '__main__':unittest.main()
