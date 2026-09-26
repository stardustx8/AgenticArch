"""Owner notifications and replies through the self-hosted ntfy server.

Replies arrive either from ntfy action buttons (the phone POSTs a short command
to the reply topic) or from `aa answer` on the workstation (written to the DB).
Reply grammar, one line: `<verb> <id> <value...>`, e.g. `tier t0925-ab12c bounded`.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from typing import Iterable

from .config import Config
from .db import DB


class Notifier:
    def __init__(self, cfg: Config, db: DB):
        self.cfg, self.db = cfg, db
        n = cfg['ntfy']
        self.enabled = bool(n.get('enabled', True))
        self.url, self.public = n['url'].rstrip('/'), n['public_url'].rstrip('/')
        self.topic, self.reply_topic = n['topic'], n['reply_topic']

    def send(self, title: str, message: str, *, choices: Iterable[tuple[str, str]] = (),
             priority: int = 3, tags: str = '') -> None:
        """Push a notification; `choices` are (label, reply-command) action buttons."""
        self.db.event('notify', title=title, message=message[:500])
        if not self.enabled:
            print(f'[notify] {title}: {message}', file=sys.stderr)
            return
        actions = [{'action': 'http', 'label': label[:20], 'method': 'POST',
                    'url': f'{self.public}/{self.reply_topic}', 'body': body, 'clear': True}
                   for label, body in list(choices)[:3]]
        body = {'topic': self.topic, 'title': title[:200], 'message': message[:3500],
                'priority': priority}
        if tags:
            body['tags'] = [t for t in tags.split(',') if t]
        if actions:
            body['actions'] = actions
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json'}, method='POST')
        try:
            urllib.request.urlopen(req, timeout=10).read()
        except OSError as exc:  # Never let a notification failure stop the state machine.
            self.db.event('notify_failed', error=str(exc))

    def poll_replies(self) -> list[str]:
        """Return new reply lines from the ntfy reply topic (and remember the cursor)."""
        if not self.enabled:
            return []
        since = self.db.kv_get('ntfy_since')
        if since is None:  # First start: ignore anything published before this daemon existed.
            since = str(int(time.time()))
            self.db.kv_set('ntfy_since', since)
        url = f'{self.url}/{self.reply_topic}/json?poll=1&since={since}'
        try:
            raw = urllib.request.urlopen(url, timeout=10).read().decode()
        except OSError:
            return []
        out = []
        for line in raw.splitlines():
            try:
                msg = json.loads(line)
            except ValueError:
                continue
            if msg.get('event') != 'message':
                continue
            self.db.kv_set('ntfy_since', msg['id'])
            if msg.get('message'):
                out.append(msg['message'].strip())
        return out
