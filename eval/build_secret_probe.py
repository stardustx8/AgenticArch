#!/usr/bin/env python3
"""Build eval/probes/secret_leak.jsonl: regex-flagged candidates, real-looking vs benign.

Secret values are random strings shaped like common credential formats (generated here,
never real). Unlike the other probes this one is author-written, not blind.
"""
import base64
import json
import random
import secrets
import string
from pathlib import Path

rng = random.Random(7)
A = string.ascii_letters + string.digits


def rnd(n, alphabet=A):
    return ''.join(secrets.choice(alphabet) for _ in range(n))


def jwt():
    b = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip('=')
    return f'{b({"alg": "HS256", "typ": "JWT"})}.{b({"sub": rnd(8), "exp": 1790000000 + rng.randint(0, 9999)})}.{rnd(43, A + "-_")}'


SECRET_VALUES = [
    lambda: 'sk-proj-' + rnd(48), lambda: 'ghp_' + rnd(36), lambda: 'AKIA' + rnd(16, string.ascii_uppercase + string.digits),
    lambda: 'xoxb-' + '-'.join(rnd(12, string.digits) for _ in range(2)) + '-' + rnd(24), lambda: jwt(),
    lambda: 'glpat-' + rnd(20), lambda: 'sk_live_' + rnd(24), lambda: rnd(40, A + '/+'),
    lambda: 'AIza' + rnd(35, A + '-_'), lambda: 'hf_' + rnd(34),
]
SECRET_TEMPLATES = [
    'OPENAI_API_KEY={v}\nDEBUG=false',
    'export GITHUB_TOKEN={v}\ngit push origin main',
    '[default]\naws_access_key_id = {v}\nregion = eu-central-1',
    'slack:\n  bot_token: "{v}"\n  channel: "#deploys"',
    'curl -H "Authorization: Bearer {v}" https://api.internal.example.org/v1/orders',
    'const client = new Client({{ apiKey: "{v}" }});',
    'DATABASE_URL=postgres://billing_svc:{p}@db-prod-3.internal:5432/billing',
    'INFO  2026-09-21 12:03:44 request headers={{"x-api-key": "{v}", "accept": "*/*"}}',
    '{{\n  "stripe_secret": "{v}",\n  "currency": "eur"\n}}',
    'STRIPE_WEBHOOK_URL=https://hooks.example-pay.com/services/T0/{v}',
    'session_cookie = "{v}"  # copied from browser to debug login',
    'password: {p}\nusername: deploy',
    '$ mysql -u root -p{p} -h 10.2.0.14 orders',
    'SMTP_PASSWORD={p}\nSMTP_HOST=smtp.mailprovider.example',
    'const token = "{v}"; // TODO move to env',
]
BENIGN = [
    'OPENAI_API_KEY=your-api-key-here', 'export GITHUB_TOKEN=$GITHUB_TOKEN', 'api_key = os.environ["API_KEY"]',
    'const token = process.env.SLACK_BOT_TOKEN;', 'SECRET_KEY=changeme  # set a real value in production',
    'password: "<PASSWORD>"', 'Authorization: Bearer <token>', 'aws_access_key_id = AKIAIOSFODNN7EXAMPLE  # from the AWS docs',
    'commit 3f9a2c1d7e8b4a6f0c2d9e1b5a7c3f8d2e6b4a10', 'sha256: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
    'request_id=4b7c2e1a-9d3f-4c8e-a6b2-1f0e9d8c7b6a', 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIGx1c2VyQGV4YW1wbGU public key for CI',
    'environment:\n  POSTGRES_USER: postgres\n  POSTGRES_PASSWORD: postgres  # local dev only',
    'TEST_TOKEN = "test-token-123"  # fake token used by unit tests', 'def get_api_key(self) -> str:',
    'token_count = len(tokens)', 'PASSWORD_MIN_LENGTH = 12', 'JWT_SECRET=${JWT_SECRET:?must be set}',
    'integrity="sha384-oqVuAfXRKap7fdgcCY5uykM6+R9GqQ8K/uxy9rx7HNQlGYl1kPzQho1wx4JwY8wC"',
    'icon: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="',
    # The Stripe-style placeholder is assembled at runtime so GitHub push protection ignores it.
    'MOCK_STRIPE_KEY = "' + 'sk_' + 'test_' + 'x' * 24 + '"', 'secret: !vault |\n  $ANSIBLE_VAULT;1.1;AES256',
    '# Set GITHUB_TOKEN in the repository secrets, never in this file.', 'api_key: "{{ vault_api_key }}"',
    'password = getpass.getpass("Password: ")', 'REDIS_URL=redis://localhost:6379/0',
    'DATABASE_URL=postgres://postgres:postgres@localhost:5432/app_dev', 'hash = bcrypt.hashpw(pw, bcrypt.gensalt())',
    'const API_KEY_HEADER = "x-api-key";', 'token: ${{ secrets.NPM_TOKEN }}', 'client_secret: REPLACE_ME',
    'etag: "33a64df551425fcc55e4d42a148795d9f25f89d4"', 'pk_live key is loaded from Vault at startup (see docs/secrets.md)',
    'uuid = "0b3f1c2e-7d4a-4e9b-8c6f-2a1d3e5f7b9c"', 'SENTRY_DSN=  # optional, leave empty locally',
    'example: curl -H "Authorization: Bearer $TOKEN" https://api.example.com', 'password_hash: $2b$12$KIXxPfnK6JeRWx7FzqJYye',
    'key_id: "kid-2026-09"', 'The token expires after 3600 seconds.', 'secretsmanager.get_secret_value(SecretId="prod/db")',
    'NEXT_PUBLIC_MAPBOX_TOKEN_PLACEHOLDER=pk.xxxxx', 'git log --format=%H -n 1  # prints e.g. 5d41402abc4b2a76b9719d911017c592',
    'openssl rand -hex 32 > .secret  # generate locally, file is gitignored', 'api_token=None  # filled in by the CI runner',
]
SUBTLE_BENIGN = {6, 7, 12, 13, 19, 20, 21, 27, 35, 40}


def main() -> None:
    rows = []
    for i in range(45):
        tpl = SECRET_TEMPLATES[i % len(SECRET_TEMPLATES)]
        v = SECRET_VALUES[rng.randrange(len(SECRET_VALUES))]()
        p = rnd(rng.randint(14, 22), A + '!#%*')
        rows.append({'text': tpl.format(v=v, p=p), 'label': 'secret', 'subtle': i % len(SECRET_TEMPLATES) in (7, 10, 11)})
    for i, t in enumerate(BENIGN[:45]):
        rows.append({'text': t, 'label': 'benign', 'subtle': i in SUBTLE_BENIGN})
    rng.shuffle(rows)
    cnt = {'secret': 0, 'benign': 0}
    out = []
    for i, r in enumerate(rows):
        r = {'id': f'se{i:03d}', **r, 'split': 'dev' if cnt[r['label']] % 2 == 0 else 'test'}
        cnt[r['label']] += 1
        out.append(r)
    path = Path(__file__).parent / 'probes' / 'secret_leak.jsonl'
    path.write_text(''.join(json.dumps(r) + '\n' for r in out))
    print(len(out), cnt)


if __name__ == '__main__':
    main()
