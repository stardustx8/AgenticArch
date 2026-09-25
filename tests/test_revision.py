from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import copy
import json
import unittest
from unittest.mock import Mock
from reference.clm import CLMClient, loopback_url, prepare_request, parse_choice, canonical_digest
from reference.routing import validate_catalog, eligible_routes, request_parts, resolve_advice, effort_options
from reference.effort import EffortGate
from reference.quota import QuotaSnapshot, attributable_delta, api_cost_to_quota
from reference.core import Lane, route, after_failure, convergence_errors, validate_policy
from test_core import valid_case, POLICY
ROOT=Path(__file__).resolve().parents[1]
CAT=json.loads((ROOT/'config/model-routing.json').read_text())
D='a'*64


def bindings(harness='codex'):
    return {key:dict(harness=harness,model_id=CAT['models'][r['model']]['identity'],
        effort=r['effort'],method=r['methods'][0],billing_mode='subscription',expires_at=100,
        available=True,permission_verified=True,identity_verified=True,integration_tested=True,
        extra_usage_disabled=True,quota_exhausted=False,fallback_detected=False)
        for key,r in CAT['routes'].items()}


def candidates(b=None, **kw):
    return eligible_routes(CAT, b if b is not None else bindings(),role='implementation',
        tier=2,harness='codex',now=1,**kw)


class RoutingRevisionTests(unittest.TestCase):
    def test_catalog(self): validate_catalog(CAT)
    def test_exact_model_identity(self):
        c=copy.deepcopy(CAT);c['models']['opus']['identity']='claude-opus-other'
        with self.assertRaises(ValueError): validate_catalog(c)
    def test_opus_extra_effort_denied(self):
        c=copy.deepcopy(CAT);c['models']['opus']['allowed_efforts'].append('max')
        with self.assertRaises(ValueError): validate_catalog(c)
    def test_wrong_provider_method_denied(self):
        c=copy.deepcopy(CAT);c['routes']['opus_high']['methods']=['codex_subscription']
        with self.assertRaises(ValueError): validate_catalog(c)
    def test_automatic_successor_denied(self):
        c=copy.deepcopy(CAT);c['models']['fable_next']['automatic_activation']=True
        with self.assertRaises(ValueError): validate_catalog(c)
    def test_participant_policy_cannot_broaden(self):
        p=copy.deepcopy(POLICY);p['debate']['claude_models'].append('claude-fable-5-5')
        with self.assertRaises(ValueError): validate_policy(p)
    def test_no_quota_conversion_policy(self):
        p=copy.deepcopy(POLICY);p['billing']['api_to_quota_conversion']=True
        with self.assertRaises(ValueError): validate_policy(p)
    def test_effective_effort_guard_required(self):
        p=copy.deepcopy(POLICY);p['effort']['effective_setting_readback_required']=False
        with self.assertRaises(ValueError): validate_policy(p)
    def test_medium_peers(self): self.assertEqual(set(candidates()),{'astra_high','opus_medium','opus_high'})
    def test_opus_is_real_peer_in_core(self):
        self.assertEqual(route('medium_tough',advice=Lane.OPUS_HIGH).lane,Lane.OPUS_HIGH)
        self.assertEqual(route('medium_tough',current=Lane.OPUS_HIGH,advice=Lane.ASTRA_HIGH).lane,Lane.ASTRA_HIGH)
    def test_opus_failure_goes_to_pro_not_another_peer(self):
        self.assertEqual(after_failure(Lane.OPUS_MEDIUM,lane_passes=2,total_passes=2,
            no_progress_passes=2,cause='code',has_hypothesis=False,policy=POLICY)[1],Lane.PRO_WEB)
    def test_architecture_only_pro(self): self.assertEqual(set(candidates(categories=('architecture',))),{'pro_web'})
    def test_both_deep_partners(self):
        self.assertEqual(set(eligible_routes(CAT,bindings(),role='deep_partner',tier=3,harness='codex',now=1)),{'fable_review','opus_review'})
    def test_api_billing_rejected(self):
        b=bindings();b['astra_high']['billing_mode']='api';self.assertNotIn('astra_high',candidates(b))
    def test_qualification_flags_fail_closed(self):
        for flag in ('available','permission_verified','identity_verified','integration_tested','extra_usage_disabled'):
            b=bindings();b['astra_high'][flag]=False
            with self.subTest(flag=flag):self.assertNotIn('astra_high',candidates(b))
    def test_expiry_identity_effort_and_exhaustion(self):
        for key,value in [('expires_at',0),('model_id','wrong'),('effort','max'),('quota_exhausted',True),('fallback_detected',True)]:
            b=bindings();b['astra_high'][key]=value
            with self.subTest(key=key):self.assertNotIn('astra_high',candidates(b))
    def test_native_pi_openai_needs_its_own_permission(self):
        b=bindings('pi');b['astra_high']['method']='pi_openai_subscription'
        self.assertNotIn('astra_high',eligible_routes(CAT,b,role='implementation',tier=2,harness='pi',now=1))
        b['astra_high']['native_subscription_permission_verified']=True
        self.assertIn('astra_high',eligible_routes(CAT,b,role='implementation',tier=2,harness='pi',now=1))
    def test_native_pi_claude_not_eligible(self):
        b=bindings('pi');b['opus_high']['method']='claude_oauth_pi'
        self.assertNotIn('opus_high',eligible_routes(CAT,b,role='implementation',tier=2,harness='pi',now=1))
    def test_pending_not_enabled(self):
        self.assertEqual(CAT['models']['fable_next']['allowed_efforts'],[])
        with self.assertRaises(ValueError):effort_options(CAT,'fable_next',minimum='high')
    def test_model_catalog_cannot_smuggle_new_effort(self):
        c=copy.deepcopy(CAT);c['models']['luna']['allowed_efforts'].append('max')
        with self.assertRaises(ValueError):validate_catalog(c)
    def test_floor_role_cannot_be_changed_in_catalog(self):
        c=copy.deepcopy(CAT);c['routes']['pro_web']['tier']=0
        with self.assertRaises(ValueError):validate_catalog(c)
    def test_compact_state_has_constraints_and_abstain(self):
        state,q,opts=request_parts(dict(goal='G',next_step='N',constraints='C',evidence_summary='E'),candidates())
        self.assertIn('constraints: C',state);self.assertIn('ABSTAIN',opts)
    def test_missing_evidence_not_synthesized(self):
        with self.assertRaises(ValueError):request_parts({'goal':'G'},candidates())
    def test_no_route_is_not_api_fallback(self): self.assertEqual(candidates({}),{})
    def test_joint_effort_menus(self):
        self.assertEqual(set(effort_options(CAT,'luna',minimum='high',max_generations=2)),{'high_for_1','high_for_2'})
        self.assertEqual(len(effort_options(CAT,'opus',minimum='medium')),8)
    def test_deep_review_cannot_use_medium(self):
        with self.assertRaises(ValueError):effort_options(CAT,'opus',minimum='medium',role='deep_partner')
    def test_pro_has_no_api_effort(self):
        with self.assertRaises(ValueError):effort_options(CAT,'pro',minimum='high')


class CLMRevisionTests(unittest.TestCase):
    def request(self):
        return prepare_request('Observed state','Which route?',{'A':'First action','ABSTAIN':'Insufficient evidence'},
            model='pinned-clm',count_tokens=lambda text:len(text.split()),max_tokens=2048)
    def body(self):return {'model':'pinned-clm','answers':{'route':{'type':'choice','choice':'A',
        'confidence':0.6,'probabilities':{'A':0.8,'ABSTAIN':0.2}}}}
    def test_wire_shape_and_normalization(self):
        r=self.request();c=parse_choice(self.body(),r,D)
        self.assertEqual(c.selected,'A');self.assertEqual(c.request_digest,canonical_digest(r))
    def test_loopback_only(self):
        for url in ('https://example.com','http://localhost:8700','http://127.1:8700',
                    'http://127.0.0.1:8700/path','http://user@127.0.0.1:8700','http://127.0.0.1:8700?x=1'):
            with self.subTest(url=url),self.assertRaises(ValueError):loopback_url(url)
        self.assertEqual(loopback_url('http://[::1]:8700/'),'http://[::1]:8700')
    def test_question_is_counted_at_tail(self):
        with self.assertRaises(ValueError):prepare_request('s','long question',{'a':'A','b':'B'},model='m',count_tokens=len,max_tokens=5)
    def test_actions_are_counted(self):
        with self.assertRaises(ValueError):prepare_request('s','q',{'a':'A'*50,'b':'B'},model='m',count_tokens=len,max_tokens=10)
    def test_invalid_tokenizer_rejected(self):
        for val in (0,True,2.1,-1):
            with self.subTest(val=val),self.assertRaises(ValueError):prepare_request('s','q',{'a':'A','b':'B'},model='m',count_tokens=lambda _:val,max_tokens=10)
    def test_duplicate_action_text_rejected(self):
        with self.assertRaises(ValueError):prepare_request('s','q',{'a':'same','b':'same'},model='m',count_tokens=len,max_tokens=10)
    def test_wrong_shape_probability_or_argmax(self):
        variants=[]
        b=self.body();b['model']='wrong';variants.append(b)
        for val in (True,float('nan'),float('inf'),-1,1.2,0.3):
            b=self.body();b['answers']['route']['probabilities']['A']=val;variants.append(b)
        b=self.body();b['answers']['route']['choice']='ABSTAIN';variants.append(b)
        b=self.body();b['answers']['route']['confidence']=0.8;variants.append(b)
        for b in variants:
            with self.subTest(body=b),self.assertRaises(ValueError):parse_choice(b,self.request(),D)
    def test_shadow_or_unqualified_never_dispatches(self):
        r=self.request();c=parse_choice(self.body(),r,D)
        for mode,qualified in [('shadow',True),('advisory',False)]:
            self.assertIsNone(resolve_advice(c,{'A':{}},mode=mode,qualified_workload=qualified,
                expected_request_digest=c.request_digest,expected_deployment_digest=D))
    def test_stale_result_rejected(self):
        c=parse_choice(self.body(),self.request(),D)
        with self.assertRaises(ValueError):resolve_advice(c,{'A':{}},mode='advisory',qualified_workload=True,
            expected_request_digest='b'*64,expected_deployment_digest=D)
    def test_valid_advice_still_only_returns_id(self):
        c=parse_choice(self.body(),self.request(),D)
        self.assertEqual(resolve_advice(c,{'A':{}},mode='advisory',qualified_workload=True,
            expected_request_digest=c.request_digest,expected_deployment_digest=D),'A')
    def test_ties_abstain(self):
        b=self.body();b['answers']['route'].update(confidence=0,probabilities={'A':.5,'ABSTAIN':.5})
        c=parse_choice(b,self.request(),D)
        self.assertIsNone(resolve_advice(c,{'A':{}},mode='advisory',qualified_workload=True,
            expected_request_digest=c.request_digest,expected_deployment_digest=D))
    def test_deployment_change_prevents_network(self):
        client=CLMClient('http://127.0.0.1:8700','m',deployment=D,deployment_digest=lambda:'b'*64,count_tokens=len)
        client._opener=Mock()
        with self.assertRaises(ValueError):client.score('s','q',{'a':'A','b':'B'})
        client._opener.open.assert_not_called()


class EffortRevisionTests(unittest.TestCase):
    def gate(self):return EffortGate('session','gpt-6-luna',('low','high'))
    def activate(self,g,n=2):
        l=g.propose('high',n,D);g.acknowledge(l,session_id='session',model_id='gpt-6-luna',effort='high',next_generation=g.next_generation);return l
    def test_cannot_start_without_ack(self):
        g=self.gate();g.propose('high',2,D)
        with self.assertRaises(ValueError):g.begin()
    def test_lease_counts_generations(self):
        g=self.gate();self.activate(g)
        for _ in range(2):self.assertEqual(g.begin(),'high');g.finish()
        with self.assertRaises(ValueError):g.begin()
    def test_no_mid_generation_update(self):
        g=self.gate();self.activate(g);g.begin()
        with self.assertRaises(ValueError):g.propose('low',1,D)
    def test_no_overlapping_generations(self):
        g=self.gate();self.activate(g);g.begin()
        with self.assertRaises(ValueError):g.begin()
    def test_clamped_effort_blocks(self):
        g=self.gate();l=g.propose('high',2,D)
        with self.assertRaises(ValueError):g.acknowledge(l,session_id='session',model_id='gpt-6-luna',effort='low',next_generation=0)
        with self.assertRaises(ValueError):g.begin()
    def test_all_invalidators(self):
        for event in ('new_input','tool_failure','model_change','scope_change','resume','policy_change','deployment_change'):
            g=self.gate();self.activate(g);g.invalidate(event)
            with self.subTest(event=event),self.assertRaises(ValueError):g.begin()
    def test_manual_wins_until_released(self):
        g=self.gate();g.invalidate('manual_override',manual='low')
        with self.assertRaises(ValueError):g.propose('high',1,D)
        g.invalidate('manual_override',manual=None);g.propose('high',1,D)
    def test_late_ack_cannot_revive_lease(self):
        g=self.gate();l=g.propose('high',1,D);g.invalidate('resume')
        with self.assertRaises(ValueError):g.acknowledge(l,session_id='session',model_id='gpt-6-luna',effort='high',next_generation=0)
    def test_failed_generation_invalidates(self):
        g=self.gate();self.activate(g);g.begin();g.finish(failed=True)
        with self.assertRaises(ValueError):g.begin()
    def test_unapproved_menus(self):
        for effort,n in [('max',2),('high',100),('high',True)]:
            with self.subTest(effort=effort,n=n),self.assertRaises(ValueError):self.gate().propose(effort,n,D)
    def test_native_checkpoint_contract(self):
        spec=spec_from_file_location('checkpoint',ROOT/'harnesses/codex/checkpoint_adapter.py')
        m=module_from_spec(spec);spec.loader.exec_module(m)
        g=self.gate();l=g.propose('high',1,D);applied=Mock()
        m.apply_checkpoint(g,l,apply_settings=applied,capture_settings=lambda:dict(session_id='session',model_id='gpt-6-luna',effort='high',next_generation=0))
        applied.assert_called_once();self.assertEqual(g.begin(),'high')


class QuotaRevisionTests(unittest.TestCase):
    def pair(self):
        return (QuotaSnapshot('a','coding','window','units',10,100,100,True),
                QuotaSnapshot('a','coding','window','units',12,110,110,True))
    def test_observed_delta(self):self.assertEqual(attributable_delta(*self.pair(),exclusive=True),2)
    def test_inexact_default_is_unknown(self):
        b,a=self.pair();self.assertIsNone(attributable_delta(b,replace(a,exact=False),exclusive=True))
    def test_reset_bucket_concurrent_stale_rejected(self):
        b,a=self.pair()
        for change in ({'window_id':'new'},{'bucket':'other'},{'used':9},{'observed_at':1000},{'used':float('nan')}):
            with self.subTest(change=change):self.assertIsNone(attributable_delta(b,replace(a,**change),exclusive=True))
        self.assertIsNone(attributable_delta(b,a,exclusive=False))
    def test_api_conversion_forbidden(self):
        with self.assertRaises(ValueError):api_cost_to_quota(.42)


class ParticipantRevisionTests(unittest.TestCase):
    def test_opus_can_replace_peer_in_new_evidence(self):
        c=valid_case();rs=[replace(r,model_id='claude-opus-5-5') if r.role=='claude' else r for r in c.receipts]
        self.assertEqual(convergence_errors(replace(c,claude_model_id='claude-opus-5-5',receipts=rs)),[])
    def test_changed_model_invalidates_old_approval(self):
        self.assertIn('participant_model_mismatch',convergence_errors(replace(valid_case(),claude_model_id='claude-opus-5-5')))
    def test_epoch_invalidates_old_reviews_without_erasing_history(self):
        self.assertIn('missing_pro_review',convergence_errors(replace(valid_case(),review_epoch=2)))
    def test_unreleased_participant_denied(self):
        self.assertIn('invalid_claude_participant',convergence_errors(replace(valid_case(),claude_model_id='claude-fable-5-5')))


if __name__=='__main__':unittest.main()
