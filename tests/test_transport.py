from dataclasses import replace
from pathlib import Path
import copy
import json
import unittest
from reference.core import ProTransportCapability, pro_transport_action, validate_policy

ROOT = Path(__file__).resolve().parents[1]


class TransportGateTests(unittest.TestCase):
    def test_no_export_without_authorization(self):
        self.assertEqual(pro_transport_action(ProTransportCapability()), 'WAIT_PERMISSION')

    def test_default_is_manual_not_unattended(self):
        cap = ProTransportCapability(export_authorized=True)
        self.assertEqual(pro_transport_action(cap), 'WAIT_MANUAL_TRANSFER')
        self.assertEqual(pro_transport_action(replace(cap, unattended_required=True)), 'WAIT_CAPABILITY')

    def test_working_tool_does_not_imply_permission(self):
        cap = ProTransportCapability(mode='supported_ui', export_authorized=True,
            local_tool_verified=True, first_send_and_continuation_verified=True)
        self.assertEqual(pro_transport_action(cap), 'WAIT_CAPABILITY')

    def test_each_gate_is_required(self):
        cap = ProTransportCapability(mode='supported_ui', export_authorized=True,
            local_tool_verified=True, first_send_and_continuation_verified=True,
            platform_permits_chatgpt_automation=True, permission_evidence_ref='trusted:test-receipt')
        self.assertEqual(pro_transport_action(cap), 'READY_FOR_PERMITTED_UI')
        for field, value in (('local_tool_verified', False), ('first_send_and_continuation_verified', False),
                             ('platform_permits_chatgpt_automation', False), ('permission_evidence_ref', '')):
            with self.subTest(field=field):
                self.assertEqual(pro_transport_action(replace(cap, **{field: value})), 'WAIT_CAPABILITY')

    def test_unknown_transport_rejected(self):
        with self.assertRaises(ValueError):
            pro_transport_action(ProTransportCapability(mode='api_substitute'))

    def test_string_boolean_rejected(self):
        with self.assertRaises(ValueError):
            pro_transport_action(ProTransportCapability(export_authorized='true'))

    def test_policy_cannot_disable_transport_guards(self):
        base = json.loads((ROOT / 'config/policy.json').read_text())
        for field, value in (('default', 'supported_ui'), ('no_restriction_bypass', False),
                             ('automatic_requires_permitted_capability', False), ('no_silent_model_substitution', False)):
            policy = copy.deepcopy(base); policy['pro_transport'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): validate_policy(policy)

    def test_exact_skill_names(self):
        base = json.loads((ROOT / 'config/policy.json').read_text())
        for field in ('pro', 'fable'):
            policy = copy.deepcopy(base)
            if field == 'pro': policy['lanes']['pro_web']['skill'] = 'wrong-skill'
            else: policy['debate']['skill'] = 'wrong-skill'
            with self.subTest(field=field), self.assertRaises(ValueError): validate_policy(policy)


if __name__ == '__main__':
    unittest.main()
