"""Participant-binding regressions from PR #1 (integration/clm-participant-policy-20260925),
ported to main's integrated API: role 'claude', Receipt.model_id, CaseReview.claude_model_id
and review_epoch. See docs/INTEGRATION-RECONCILIATION-2026-09-25.md."""
from dataclasses import replace
import unittest
from test_core import valid_case
from reference.core import convergence_errors


class ParticipantTests(unittest.TestCase):
    def test_opus_is_a_valid_equal_partner(self):
        case = valid_case()
        case = replace(case, claude_model_id='claude-opus-5-5', receipts=[
            replace(r, model_id='claude-opus-5-5') if r.role == 'claude' else r
            for r in case.receipts])
        self.assertEqual(convergence_errors(case), [])

    def test_partner_switch_invalidates_old_approvals(self):
        self.assertTrue(convergence_errors(replace(valid_case(), claude_model_id='claude-opus-5-5')))

    def test_new_binding_invalidates_old_approvals(self):
        # PR #1 expressed a new session binding as a changed digest; main expresses any
        # identity/configuration change as a new review epoch.
        self.assertTrue(convergence_errors(replace(valid_case(), review_epoch=2)))

    def test_missing_identity_cannot_converge(self):
        self.assertIn('invalid_claude_participant',
                      convergence_errors(replace(valid_case(), claude_model_id='')))

    def test_unreleased_successor_not_allowed(self):
        self.assertIn('invalid_claude_participant',
                      convergence_errors(replace(valid_case(), claude_model_id='claude-fable-5-5')))

    def test_receipt_from_other_model_does_not_count(self):
        case = valid_case()
        case = replace(case, receipts=[
            replace(r, model_id='claude-opus-5-5') if r.role == 'claude' else r
            for r in case.receipts])
        self.assertIn('participant_model_mismatch', convergence_errors(case))


if __name__ == '__main__':
    unittest.main()
