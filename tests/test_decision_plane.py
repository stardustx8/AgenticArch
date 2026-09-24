import copy
import json
import unittest
from pathlib import Path
from reference.decision_plane import (
    canonical, digest, stages, make_request, shared_state_groups,
    interpret, validate_operator, REQUIRED_CONTEXT, request_is_intact,
)
ROOT = Path(__file__).resolve().parents[1]


class DecisionPlaneTests(unittest.TestCase):
    def setUp(self):
        self.ops = json.loads((ROOT/'config/decision-operators.json').read_text())['operators']
        self.op = copy.deepcopy(self.ops[0])
        self.context = {k: 'a'*64 if k.endswith('_digest') else 'synthetic-test'
                        for k in REQUIRED_CONTEXT}
        self.context['max_options'] = 16
        self.state = {'goal':'fix a scoped issue', 'requirements':['preserve behavior'],
                      'candidate':{'path':'src/jobs.py', 'revision':'test'},
                      'unrelated_private_field':'must not appear'}

    def request(self):
        return make_request(self.op, self.state, self.context, event='context_ready')

    def response(self, request=None):
        req = request or self.request()
        return {'request_id':req['request_id'], 'selected':'relevant',
                'scores':{'relevant':.8,'possibly_stale':.1,'unrelated':.05,'insufficient':.05}}

    def test_catalog_valid_and_shadow(self):
        for op in self.ops:
            validate_operator(op)
            self.assertEqual(op['mode'], 'shadow')
        self.assertEqual(len(stages(self.ops)), 1)

    def test_canonical_key_order(self):
        self.assertEqual(digest({'a':1,'b':2}), digest({'b':2,'a':1}))

    def test_bad_json_rejected(self):
        for value in [float('nan'), float('inf'), {1:'x'}, (1,2), {1,2}, b'abc']:
            with self.subTest(value=repr(value)), self.assertRaises(ValueError):
                canonical(value)

    def test_projection_excludes_unrelated(self):
        req = self.request()
        self.assertNotIn('unrelated_private_field', req['state'])
        self.assertNotIn('must not appear', str(req))

    def test_mutation_does_not_alter_snapshot(self):
        req = self.request()
        self.state['requirements'].append('new')
        self.assertEqual(req['state']['requirements'], ['preserve behavior'])
        self.assertTrue(request_is_intact(req))

    def test_scoped_state_changes_identity(self):
        old = self.request()['request_id']
        self.state['candidate']['revision'] = 'new'
        self.assertNotEqual(old, self.request()['request_id'])

    def test_all_context_changes_invalidate(self):
        old = self.request()['request_id']
        for key in REQUIRED_CONTEXT:
            context = dict(self.context)
            context[key] = 'b'*64 if key.endswith('_digest') else 'changed'
            with self.subTest(key=key):
                req = make_request(self.op, self.state, context, event='context_ready')
                self.assertNotEqual(old, req['request_id'])

    def test_option_order_changes_identity(self):
        old = self.request()['request_id']
        self.op['options'].reverse()
        self.assertNotEqual(old, self.request()['request_id'])

    def test_missing_projection_fails(self):
        del self.state['candidate']
        with self.assertRaises(ValueError): self.request()

    def test_unknown_trigger_fails(self):
        with self.assertRaises(ValueError):
            make_request(self.op, self.state, self.context, event='random_tick')

    def test_disabled_operator_fails(self):
        self.op['mode'] = 'off'
        with self.assertRaises(ValueError): self.request()

    def test_missing_context_fails(self):
        del self.context['authorization_scope_digest']
        with self.assertRaises(ValueError): self.request()

    def test_bad_digest_fails(self):
        self.context['snapshot_digest'] = 'not-a-digest'
        with self.assertRaises(ValueError): self.request()

    def test_backend_limit_fails(self):
        self.context['max_options'] = 2
        with self.assertRaises(ValueError): self.request()

    def test_bool_backend_limit_fails(self):
        self.context['max_options'] = True
        with self.assertRaises(ValueError): self.request()

    def test_authorization_influence_rejected(self):
        self.op['allowed_influence'] = 'authorize_upload'
        with self.assertRaises(ValueError): self.request()

    def test_abstention_option_required(self):
        self.op['options'] = self.op['options'][:-1]
        with self.assertRaises(ValueError): self.request()

    def test_duplicate_options_rejected(self):
        self.op['options'][1]['id'] = self.op['options'][0]['id']
        with self.assertRaises(ValueError): self.request()

    def test_groups_share_only_identical_state_and_context(self):
        req = self.request()
        other = copy.deepcopy(self.op); other['id'] = 'different_question'
        other['question'] = 'A different atomic question'
        second = make_request(other, self.state, self.context, event='context_ready')
        self.assertEqual(len(shared_state_groups([req, second])),1)
        self.context['project_id'] = 'other-project'
        third = make_request(other, self.state, self.context, event='context_ready')
        self.assertEqual(len(shared_state_groups([req, third])),2)

    def test_same_request_not_batched_twice(self):
        req = self.request()
        with self.assertRaises(ValueError): shared_state_groups([req, req])

    def test_dependencies_need_later_stage(self):
        second = copy.deepcopy(self.op); second['id'] = 'second'
        second['depends_on'] = [self.op['id']]
        self.assertEqual(stages([self.op,second]), [[self.op['id']],['second']])
        req2 = make_request(second, self.state, self.context, event='context_ready')
        with self.assertRaises(ValueError): shared_state_groups([self.request(),req2])

    def test_dependency_cycle_rejected(self):
        self.op['depends_on'] = [self.op['id']]
        with self.assertRaises(ValueError): stages([self.op])

    def test_missing_dependency_rejected(self):
        self.op['depends_on'] = ['unknown']
        with self.assertRaises(ValueError): stages([self.op])

    def test_shadow_never_influences(self):
        advice = interpret(self.request(),self.response(),qualified=True)
        self.assertEqual(advice.status,'SHADOW')
        self.assertIsNone(advice.influence)

    def test_advisory_still_needs_qualification(self):
        self.op['mode'] = 'advisory'; req = self.request()
        self.assertEqual(interpret(req,self.response(req)).status,'SHADOW')
        result = interpret(req,self.response(req),qualified=True)
        self.assertEqual((result.status,result.influence),('ADVISE','rank_context'))
        self.assertEqual(result.reason,'requires_controller_validation')

    def test_invalid_qualification_not_truthy(self):
        self.op['mode']='advisory'; req=self.request()
        self.assertEqual(interpret(req,self.response(req),qualified='yes').status,'SHADOW')

    def test_wrong_request_rejected(self):
        out=self.response(); out['request_id']='b'*64
        self.assertEqual(interpret(self.request(),out).status,'ABSTAIN')

    def test_modified_request_rejected(self):
        req=self.request(); req['state']['goal']='changed'
        self.assertEqual(interpret(req,self.response()).status,'FALLBACK')

    def test_unknown_option_rejected(self):
        out=self.response(); out['scores']['upload_secrets']=0
        self.assertEqual(interpret(self.request(),out).status,'ABSTAIN')

    def test_bad_scores_rejected(self):
        for value in [True, float('nan'), float('inf'), -1, 1.1, '0.8']:
            out=self.response(); out['scores']['relevant']=value
            with self.subTest(value=repr(value)):
                self.assertEqual(interpret(self.request(),out).status,'ABSTAIN')

    def test_unnormalized_scores_rejected(self):
        out=self.response(); out['scores']['relevant']=.7
        self.assertEqual(interpret(self.request(),out).reason,'unnormalized_scores')

    def test_tie_abstains(self):
        out=self.response(); out['scores']={k:.25 for k in out['scores']}
        self.assertEqual(interpret(self.request(),out).reason,'tie')

    def test_selected_disagreement_rejected(self):
        out=self.response(); out['selected']='unrelated'
        self.assertEqual(interpret(self.request(),out).reason,'selected_option_mismatch')

    def test_insufficient_abstains(self):
        out=self.response(); out['selected']='insufficient'
        out['scores']['insufficient'],out['scores']['relevant']=.8,.05
        self.assertEqual(interpret(self.request(),out).reason,'insufficient_evidence')

if __name__ == '__main__': unittest.main()
