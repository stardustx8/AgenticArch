"""Notifier access control: tokens go into request and action-button headers."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from aa import config
from aa.db import DB
from aa.notify import Notifier


class FakeResponse:
    def __init__(self, body=b''):
        self.body = body

    def read(self):
        return self.body


class NotifierAuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.requests = []

    def notifier(self, **ntfy):
        cfg = config.load(Path('/nonexistent'), {'ntfy': ntfy})
        return Notifier(cfg, DB(':memory:'))

    def capture(self, body=b''):
        def urlopen(req, timeout):
            self.requests.append(req)
            return FakeResponse(body)
        return mock.patch('urllib.request.urlopen', urlopen)

    def test_tokens_in_send_poll_and_action_headers(self):
        (self.tmp / 'd').write_text('tk_daemon\n')
        (self.tmp / 'r').write_text('tk_phone\n')
        n = self.notifier(token_file=str(self.tmp / 'd'), reply_token_file=str(self.tmp / 'r'))
        with self.capture():
            n.send('t', 'm', choices=[('Yes', 'answer x yes')])
            n.poll_replies()
        send, poll = self.requests
        self.assertEqual(send.get_header('Authorization'), 'Bearer tk_daemon')
        self.assertEqual(poll.get_header('Authorization'), 'Bearer tk_daemon')
        action = json.loads(send.data)['actions'][0]
        self.assertEqual(action['headers'], {'Authorization': 'Bearer tk_phone'})

    def test_missing_token_files_send_no_auth(self):
        n = self.notifier(token_file=str(self.tmp / 'none'), reply_token_file=str(self.tmp / 'none'))
        with self.capture():
            n.send('t', 'm', choices=[('Yes', 'answer x yes')])
        req = self.requests[0]
        self.assertIsNone(req.get_header('Authorization'))
        self.assertNotIn('headers', json.loads(req.data)['actions'][0])


if __name__ == '__main__':
    unittest.main()
