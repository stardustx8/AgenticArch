import copy
import json
import unittest
from dataclasses import replace
from unittest.mock import MagicMock
from reference.clm import LocalCLM, normalize_choice, prepare_choice, render_state

P = dict(encoder_revision='pinned-encoder', tokenizer_revision='pinned-tokenizer',
         head_sha256='a' * 64, pooling='last-token', runtime_revision='pinned-runtime',
         renderer_version='agenticarch-prose-v1')
OPTIONS = {'luna_high': 'Bounded implementation using Luna high.',
           'insufficient': 'Insufficient evidence to recommend an implementation route.'}


def request(**kw):
    args = dict(model='owned-pinned-head', provenance=P, token_counter=lambda s: len(s.split()), max_tokens=2048)
    args.update(kw)
    return prepare_choice('Task: implement an approved bounded change.', 'Which route fits?', OPTIONS, **args)


def response(scores=None, selected='luna_high'):
    return {'model': 'owned-pinned-head', 'answers': {'decision': {'type': 'choice',
            'choice': selected, 'confidence': 0.8,
            'probabilities': scores or {'luna_high': 0.9, 'insufficient': 0.1}}}}


class CLMTests(unittest.TestCase):
    def test_prose_wire_format(self):
        body = json.loads(request().body)
        self.assertEqual(body['questions']['decision']['type'], 'choice')
        self.assertEqual(body['questions']['decision']['criteria'], OPTIONS)
        self.assertNotIn('Which route', body['state'])

    def test_structured_evidence_is_readable(self):
        self.assertEqual(render_state({'Task': 'Fix it', 'Known': ['Test fails'], 'Quota': None}),
                         'Task: Fix it\n\nKnown: - Test fails\n\nQuota: unknown')

    def test_encoder_budget(self):
        with self.assertRaises(ValueError): request(max_tokens=1)
        with self.assertRaises(ValueError): request(token_counter=lambda s: False)

    def test_head_pin(self):
        with self.assertRaises(ValueError): request(provenance={**P, 'head_sha256': 'latest'})

    def test_binding_changes(self):
        self.assertNotEqual(request().request_id,
                            request(provenance={**P, 'head_sha256': 'b' * 64}).request_id)

    def test_normalized_advice_is_not_authority(self):
        result = normalize_choice(request(), response())
        self.assertEqual(result['status'], 'SUGGEST')
        self.assertEqual(result['calibration'], 'uncalibrated')
        self.assertAlmostEqual(result['separation'], 0.8)

    def test_tie_and_abstention(self):
        self.assertEqual(normalize_choice(request(), response({'luna_high': .5, 'insufficient': .5}))['status'], 'ABSTAIN')
        self.assertEqual(normalize_choice(request(), response({'luna_high': .1, 'insufficient': .9}, 'insufficient'))['status'], 'ABSTAIN')

    def test_bad_probabilities(self):
        for scores in ({'luna_high': True, 'insufficient': 0},
                       {'luna_high': float('nan'), 'insufficient': .1},
                       {'luna_high': .9, 'insufficient': .9}, {'other': 1}):
            with self.subTest(scores=scores), self.assertRaises(ValueError):
                normalize_choice(request(), response(scores))

    def test_wrong_model_question_and_selection(self):
        for change in ('model', 'question', 'choice'):
            result = response()
            if change == 'model': result['model'] = 'different-head'
            if change == 'question': result['answers']['other'] = result['answers'].pop('decision')
            if change == 'choice': result['answers']['decision']['choice'] = 'insufficient'
            with self.subTest(change=change), self.assertRaises(ValueError): normalize_choice(request(), result)

    def test_tampered_body(self):
        with self.assertRaises(ValueError): normalize_choice(replace(request(), body=b'{}'), response())

    def test_local_transport_only(self):
        for url in ('https://example.com:8700', 'http://localhost:8700', 'http://127.0.0.1:8700/redirect',
                    'http://user@127.0.0.1:8700', 'http://127.0.0.1:8700?x=1', 'http://127.0.0.1'):
            with self.subTest(url=url), self.assertRaises(ValueError): LocalCLM(url)
        LocalCLM('http://127.0.0.1:8700')
        LocalCLM('http://[::1]:8700')

    def test_mock_http_roundtrip_and_size_limit(self):
        client = LocalCLM('http://127.0.0.1:8700')
        client._opener = MagicMock()
        reply = client._opener.open.return_value.__enter__.return_value
        reply.status = 200
        reply.read.return_value = json.dumps(response()).encode()
        self.assertEqual(client.choose(request())['selected'], 'luna_high')
        reply.read.return_value = b'x' * 262145
        with self.assertRaises(ValueError): client.choose(request())

    def test_no_secret_in_transport_failure(self):
        client = LocalCLM('http://127.0.0.1:8700', api_key='private-value')
        client._opener = MagicMock()
        client._opener.open.side_effect = OSError('private-value')
        with self.assertRaisesRegex(RuntimeError, '^Local CLM unavailable') as result: client.choose(request())
        self.assertNotIn('private-value', str(result.exception))


if __name__ == '__main__': unittest.main()
