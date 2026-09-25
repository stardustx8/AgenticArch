from dataclasses import replace
import copy
import json
from pathlib import Path
import unittest

from reference.core import (
    CaseReview, Check, Completion, Lane, Receipt, Review, after_failure,
    completion_errors, convergence_errors, debate_action, route,
    solution_digest, validate_advice, validate_lane, validate_policy,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / 'config/policy.json').read_text())
A, B, C, D = ('a' * 64, 'b' * 64, 'c' * 64, 'd' * 64)


def valid_case():
    return CaseReview('case-1', A, B, C, [
        Review('claude', 'APPROVE', A, B, C, 'f1'),
        Review('pro', 'APPROVE', A, B, C, 'p1'),
    ], [
        Receipt('f1', 'case-1', 'claude', 'claude_challenge', 1, True, True, 'claude-fable-5-1'),
        Receipt('p1', 'case-1', 'pro', 'pro_response', 2, True, True, 'gpt-6-pro-web'),
    ], manifest_verified=True, evidence_references_verified=True,
       required_deliverables_present=True, claude_model_id='claude-fable-5-1')


def valid_completion():
    return Completion(A, B, {'tests': C}, [Check('tests', A, B, C, 'PASS', 0)],
                      ['R1'], {'R1': A}, scope_ok=True, regression_coverage=True,
                      behavior_reviewed=True, delivery_completed=True)


class PolicyTests(unittest.TestCase):
    def test_policy_is_valid(self):
        validate_policy(POLICY)

    def test_four_direct_lanes(self):
        for difficulty, expected in zip(('routine', 'bounded', 'medium_tough', 'tough'),
                (Lane.LUNA_LOW, Lane.LUNA_HIGH, Lane.ASTRA_HIGH, Lane.PRO_WEB)):
            with self.subTest(difficulty=difficulty):
                self.assertEqual(route(difficulty).lane, expected)

    def test_mandatory_categories_bypass_low_advice(self):
        for category in POLICY['mandatory_pro_categories']:
            self.assertEqual(route('routine', [category], advice=Lane.LUNA_LOW).lane, Lane.PRO_WEB)

    def test_unassessed_is_assessment_only(self):
        result = route('routine', risk_assessed=False)
        self.assertTrue(result.assessment_only)
        self.assertEqual(result.lane, Lane.ASTRA_HIGH)

    def test_monotonic(self):
        self.assertEqual(route('routine', current=Lane.ASTRA_HIGH, advice=Lane.LUNA_LOW).lane,
                         Lane.ASTRA_HIGH)

    def test_advice_can_raise_floor(self):
        self.assertEqual(route('bounded', advice=Lane.ASTRA_HIGH).lane, Lane.ASTRA_HIGH)

    def test_invalid_reasoning_is_rejected(self):
        for effort in ('none', 'medium', 'max', 'xhigh', None):
            with self.subTest(effort=effort), self.assertRaises(ValueError):
                validate_lane('GPT-6 Luna', effort)
        with self.assertRaises(ValueError):
            validate_lane('GPT-6 Astra', 'low')
        with self.assertRaises(ValueError):
            validate_lane('GPT-6 Pro', 'high')

    def test_unknown_classification_is_not_routine(self):
        with self.assertRaises(ValueError):
            route('unknown')
        with self.assertRaises(ValueError):
            route('routine', ['unknown'])

    def test_weakened_policy_rejected(self):
        for group, key, value in [('clm', 'can_lower_floor', True),
                                   ('debate', 'same_chat_for_pro', False),
                                   ('verification', 'nonempty_required_checks', False)]:
            policy = copy.deepcopy(POLICY)
            policy[group][key] = value
            with self.assertRaises(ValueError):
                validate_policy(policy)

    def test_failure_retry_with_hypothesis(self):
        self.assertEqual(after_failure(Lane.LUNA_HIGH, lane_passes=1, total_passes=1,
            no_progress_passes=0, cause='code', has_hypothesis=True, policy=POLICY),
            ('RETRY', Lane.LUNA_HIGH))

    def test_exhausted_lane_escalates(self):
        self.assertEqual(after_failure(Lane.LUNA_HIGH, lane_passes=2, total_passes=2,
            no_progress_passes=1, cause='code', has_hypothesis=True, policy=POLICY),
            ('ESCALATE', Lane.ASTRA_HIGH))

    def test_total_budget_goes_to_pro(self):
        self.assertEqual(after_failure(Lane.LUNA_HIGH, lane_passes=1, total_passes=6,
            no_progress_passes=0, cause='code', has_hypothesis=True, policy=POLICY)[1], Lane.PRO_WEB)

    def test_environment_is_not_a_reasoning_failure(self):
        self.assertEqual(after_failure(Lane.LUNA_HIGH, lane_passes=2, total_passes=6,
            no_progress_passes=2, cause='environment', has_hypothesis=False, policy=POLICY)[0],
            'WAIT_ENVIRONMENT')

    def test_no_hypothesis_does_not_loop(self):
        self.assertEqual(after_failure(Lane.ASTRA_HIGH, lane_passes=1, total_passes=1,
            no_progress_passes=0, cause='code', has_hypothesis=False, policy=POLICY)[1], Lane.PRO_WEB)


class AdviceTests(unittest.TestCase):
    def data(self):
        return {'schema_version': 1, 'request_id': 'req-1', 'state_digest': A,
                'ordered_options': ['luna_low', 'luna_high'],
                'scores': {'luna_low': 0.4, 'luna_high': 0.6}, 'selected': 'luna_high',
                'calibration': 'uncalibrated',
                'provenance': {'model_revision': 'rev', 'tokenizer_revision': 'rev',
                               'backend': 'test', 'prompt_version': 'v1'}}

    def check(self, data):
        return validate_advice(data, request_id='req-1', state_digest=A,
                               ordered_options=['luna_low', 'luna_high'])

    def test_valid(self):
        self.assertEqual(self.check(self.data()), 'luna_high')

    def test_nonfinite_bool_out_of_range_and_bad_sum(self):
        for value in (float('nan'), float('inf'), -0.1, 1.1, True, 0.2):
            data = self.data(); data['scores']['luna_low'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.check(data)

    def test_unknown_selected_or_request(self):
        for field, value in [('selected', 'UNKNOWN'), ('request_id', 'stale'),
                              ('state_digest', B), ('ordered_options', ['luna_high', 'luna_low'])]:
            data = self.data(); data[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): self.check(data)

    def test_tie_uses_higher_lane(self):
        data = self.data(); data['scores'] = dict(luna_low=0.5, luna_high=0.5)
        self.assertEqual(self.check(data), 'luna_high')
        data['selected'] = 'luna_low'
        with self.assertRaises(ValueError): self.check(data)


class DigestTests(unittest.TestCase):
    def test_order_independence_and_content_sensitivity(self):
        first = {'SOLUTION.md': b'v1', 'IMPLEMENTATION.md': b'steps'}
        self.assertEqual(solution_digest(first), solution_digest(dict(reversed(list(first.items())))))
        self.assertNotEqual(solution_digest(first), solution_digest({**first, 'SOLUTION.md': b'v2'}))

    def test_paths_are_part_of_digest(self):
        self.assertNotEqual(solution_digest({'one.md': b'a'}), solution_digest({'two.md': b'a'}))

    def test_unsafe_paths(self):
        for path in ('../secret', '/absolute', 'a/../b', 'a\\b', 'a//b', 'a/./b', 'C:secret', ''):
            with self.subTest(path=path), self.assertRaises(ValueError): solution_digest({path: b'x'})

    def test_empty_and_alias_collisions(self):
        with self.assertRaises(ValueError): solution_digest({})
        with self.assertRaises(ValueError): solution_digest({'A.md': b'1', 'a.md': b'2'})


class ConvergenceTests(unittest.TestCase):
    def test_matching_actual_receipts_and_approvals(self):
        self.assertEqual(convergence_errors(valid_case()), [])

    def test_each_digest_must_match(self):
        for field in ('solution_digest', 'requirements_digest', 'bundle_digest'):
            case = valid_case()
            changed = replace(case.reviews[0], **{field: D})
            with self.subTest(field=field):
                self.assertIn('claude_stale_approval', convergence_errors(
                    replace(case, reviews=[changed, case.reviews[1]])))

    def test_blockers_and_missing_manifest(self):
        self.assertIn('unresolved_blockers', convergence_errors(replace(valid_case(), unresolved_blockers=['F1'])))
        self.assertIn('manifest_verified', convergence_errors(replace(valid_case(), manifest_verified=False)))

    def test_latest_verdict_wins_not_an_old_approval(self):
        case = valid_case()
        receipt = Receipt('f2', case.case_id, 'claude', 'review', 3, True, True, 'claude-fable-5-1')
        review = Review('claude', 'REVISE', A, B, C, 'f2')
        errors = convergence_errors(replace(case, receipts=[*case.receipts, receipt],
                                            reviews=[review, *case.reviews]))
        self.assertIn('claude_not_approved', errors)

    def test_unverified_or_wrong_case_receipt_rejected(self):
        for delta in ({'identity_verified': False}, {'case_id': 'other'},
                      {'durable_output_verified': False}):
            case = valid_case()
            errors = convergence_errors(replace(case, receipts=[replace(case.receipts[0], **delta), case.receipts[1]]))
            self.assertTrue(errors)

    def test_challenge_then_response_required(self):
        case = valid_case()
        errors = convergence_errors(replace(case, receipts=[case.receipts[0], replace(case.receipts[1], phase='initial')]))
        self.assertIn('missing_real_challenge_then_response', errors)

    def test_duplicate_receipt_rejected(self):
        case = valid_case()
        self.assertIn('duplicate_receipt', convergence_errors(replace(case, receipts=[*case.receipts, case.receipts[0]])))

    def test_new_turn_without_verdict_invalidates_old_approval(self):
        case = valid_case()
        receipt = Receipt('f2', case.case_id, 'claude', 'review', 3, True, True, 'claude-fable-5-1')
        self.assertIn('claude_latest_turn_unreviewed', convergence_errors(
            replace(case, receipts=[*case.receipts, receipt])))

    def test_budget_is_pause_not_agreement(self):
        self.assertEqual(debate_action(converged=False, rounds_this_run=6,
                         unresolved_nonprogress_rounds=0, policy=POLICY), 'PAUSED')
        self.assertEqual(debate_action(converged=False, rounds_this_run=2,
                         unresolved_nonprogress_rounds=2, policy=POLICY), 'PAUSED')
        self.assertEqual(debate_action(converged=True, rounds_this_run=6,
                         unresolved_nonprogress_rounds=0, policy=POLICY), 'LOCAL_RECONCILIATION')


class CompletionTests(unittest.TestCase):
    def test_valid_non_pro_task(self):
        self.assertEqual(completion_errors(valid_completion()), [])

    def test_nonempty_checks_and_requirements(self):
        self.assertIn('no_required_checks', completion_errors(replace(valid_completion(), required_checks={}, checks=[])))
        self.assertIn('no_acceptance_requirements', completion_errors(replace(valid_completion(), required_requirements=[])))

    def test_missing_check(self):
        self.assertIn('missing_check:tests', completion_errors(replace(valid_completion(), checks=[])))

    def test_stale_snapshot_plan_and_command(self):
        for field in ('snapshot_digest', 'plan_digest', 'command_digest'):
            state = valid_completion()
            check = replace(state.checks[0], **{field: D})
            self.assertIn('stale_or_wrong_check:tests', completion_errors(replace(state, checks=[check])))

    def test_failure_timeout_skip_and_nonzero_exit(self):
        for status, code in [('FAIL', 1), ('TIMEOUT', None), ('SKIPPED', None), ('PASS', 1), ('PASS', False)]:
            state = valid_completion()
            self.assertIn('observed_check_not_passed', completion_errors(replace(
                state, checks=[replace(state.checks[0], status=status, exit_code=code)])))

    def test_duplicate_checks_do_not_hide_failure(self):
        state = valid_completion()
        errors = completion_errors(replace(state, checks=[replace(state.checks[0], status='FAIL'), *state.checks]))
        self.assertIn('duplicate_check_results', errors)
        self.assertIn('observed_check_not_passed', errors)

    def test_behavior_scope_and_delivery_are_separate_gates(self):
        for field in ('behavior_reviewed', 'scope_ok', 'regression_coverage', 'delivery_completed'):
            self.assertIn(field, completion_errors(replace(valid_completion(), **{field: False})))

    def test_requirement_evidence_must_match_current_snapshot(self):
        self.assertIn('uncovered_requirement:R1', completion_errors(replace(valid_completion(), requirement_evidence={'R1': D})))

    def test_pro_agreement_without_local_reconciliation_is_not_done(self):
        state = replace(valid_completion(), pro_required=True, case=valid_case(),
                        expected_case_id='case-1', expected_solution_digest=A,
                        expected_requirements_digest=B, expected_bundle_digest=C)
        self.assertIn('local_reconciliation_required', completion_errors(state))
        self.assertEqual(completion_errors(replace(state, local_reconciled=True)), [])

    def test_material_local_change_reopens_review(self):
        state = replace(valid_completion(), pro_required=True, case=valid_case(),
                        local_reconciled=True, material_local_change=True)
        self.assertIn('material_local_change_requires_review', completion_errors(state))

    def test_other_converged_case_does_not_complete_this_task(self):
        state = replace(valid_completion(), pro_required=True, case=valid_case(),
                        local_reconciled=True, expected_case_id='another-case',
                        expected_solution_digest=A, expected_requirements_digest=B,
                        expected_bundle_digest=C)
        self.assertIn('case_not_bound_to_local_task', completion_errors(state))

    def test_missing_or_unapproved_pro_case(self):
        state = replace(valid_completion(), pro_required=True, local_reconciled=True)
        self.assertIn('missing_pro_case', completion_errors(state))
        self.assertIn('case_not_converged', completion_errors(replace(state, case=replace(valid_case(), unresolved_blockers=['F1']))))


if __name__ == '__main__':
    unittest.main()
