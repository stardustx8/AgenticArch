from dataclasses import replace
import unittest
from test_core import valid_case
from reference.core import convergence_errors

class ParticipantTests(unittest.TestCase):
    def test_opus_is_a_valid_equal_partner(self):
        case=valid_case()
        case=replace(case,reviewer_identity='claude-opus-5-5',receipts=[
            replace(r,participant_identity='claude-opus-5-5') if r.role=='reviewer' else r
            for r in case.receipts])
        self.assertEqual(convergence_errors(case),[])
    def test_partner_switch_invalidates_old_approvals(self):
        self.assertTrue(convergence_errors(replace(valid_case(),reviewer_identity='claude-opus-5-5')))
    def test_new_binding_invalidates_old_approvals(self):
        self.assertTrue(convergence_errors(replace(valid_case(),participant_binding_digest='e'*64)))
    def test_missing_identity_cannot_converge(self):
        self.assertTrue(convergence_errors(replace(valid_case(),reviewer_identity=None)))
    def test_unreleased_successor_not_allowed(self):
        self.assertTrue(convergence_errors(replace(valid_case(),reviewer_identity='claude-fable-5-5')))
