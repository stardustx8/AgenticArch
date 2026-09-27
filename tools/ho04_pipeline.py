"""Ultra-hard existing-project fixture: offline transcript-to-summary pipeline.

Synthetic data and a stub model only; nothing here is a real customer system.
Generated from scratch trees by a local generator script,
then kept as the single source of truth for the lab.

Stage 1 (vague owner request): reliability. Hidden causes span ingest, store,
worker, export, requeue, status (Python) and ui/status.ts (TypeScript):
  - accept moves the inbox file before the job commits (crash loses the upload)
  - running jobs have a lease but nothing ever reclaims an expired one
  - non-idempotent writes: jobs per redelivered source, summaries rows, Export v1 rows
  - requeue --inline salvages malformed model output as a success (D-005)
  - every error is one `failed` state with retries, even empty/over-long input (D-006/7)
  - status.py collapses states for a UI v1, ui/status.ts only knows `failed`
Stage 2 (changed requirement): D-009 redaction approved with phone numbers,
persisted nowhere (archive, DB, export, model audit log incl. model output),
`redacted` status flag through Python and TypeScript, Export v1 byte-compatible,
in-place schema migration for the live database.
"""
from tools.ho02_projects import project

FILES = {
    'README.md': r'''# Transcript pipeline

Offline transcript-to-summary pipeline. Call recordings are transcribed
elsewhere; the uploader drops `call-<n>.txt` files into the inbox, this
pipeline turns them into validated summaries for the reporting team and keeps
an ops status page current. No network access, no real model: the model client
replays canned responses (docs/decisions.md D-001).

## Layout

| Path                    | What                                                   |
| ----------------------- | ------------------------------------------------------ |
| `pipeline/ingest.py`    | accepts inbox files as jobs, archive copy              |
| `pipeline/store.py`     | SQLite jobs + summaries, schema and migrations         |
| `pipeline/worker.py`    | claim, model call with retries, validation, writes     |
| `pipeline/requeue.py`   | puts failed jobs back, optional inline processing      |
| `pipeline/model_client.py` | stub model client and model audit log               |
| `pipeline/output.py`    | prompt contract, structured-output validation          |
| `pipeline/export.py`    | Export v1 (TSV for the reporting team, frozen format)  |
| `pipeline/status.py`    | status snapshot for the UI                             |
| `pipeline/faults.py`    | crash rehearsal checkpoints                            |
| `pipeline/legacy_batch.py` | deprecated pre-queue batch summariser (not wired)   |
| `ui/`                   | TypeScript status page model, run with node            |
| `scripts/`              | crash rehearsal                                        |
| `docs/`                 | decisions (authoritative), contracts, operations and incident notes |

## Checks

    python3 -m unittest discover -s tests -t .

The UI tests need node 22+ (type stripping). Keep public interfaces, the
Export v1 format and legacy behaviour unless a decision says otherwise, and
record what changed and what was actually verified in docs/handoff.md.
''',
    'config/pipeline.json': r'''{
  "db_path": "state/pipeline.db",
  "inbox_dir": "inbox",
  "archive_dir": "archive",
  "export_path": "out/summaries_v1.tsv",
  "status_path": "out/status.json",
  "calls_log": "state/model_calls.jsonl",
  "responses_dir": "fixtures/responses",
  "lease_seconds": 300,
  "max_transcript_chars": 20000,
  "model": {
    "name": "stub-summarizer-2",
    "max_attempts": 3,
    "backoff_seconds": [2, 10, 30]
  }
}
''',
    'docs/contracts.md': r'''# Contracts

Interfaces between the pipeline, the model and its consumers.

# Part 1: model output and Export v1

## Model output (summary JSON)

The model must return one JSON object, optionally wrapped in a ```json fence:

| key            | type                              | rule                          |
| -------------- | --------------------------------- | ----------------------------- |
| `title`        | string                            | non-empty, at most 120 chars  |
| `bullets`      | list of strings                   | 1 to 8 non-empty strings      |
| `action_items` | list of `{"owner", "task"}`       | optional, strings, task non-empty |

`pipeline/output.py` validates and normalises (strips whitespace). The stored
summary (`summaries.body`) is the normalised object with exactly these keys.

## Export v1 (frozen)

`out/summaries_v1.tsv`, UTF-8, `\n` line endings, tab separated, one header
line followed by one line per summarised job:

    job_id  source  title  bullets  action_items  model

- `bullets`: joined with ` | `
- `action_items`: each item as `owner: task`, joined with ` | `; empty if none
- tabs, newlines and repeated blanks inside a value collapse to a single space

The reporting team's importer rejects files with a different header or column
count. Do not add, remove, rename or reorder columns.

# Part 2: status (pipeline -> ops UI)

Written by `pipeline/status.py` to `out/status.json`, read by `ui/status.ts`.
Revised 2026-02-02 for D-006.

## status.json

    {
      "generated_at": <epoch seconds>,
      "counts": {<state>: <number of jobs>, ...},
      "jobs": [{"id", "source", "state", "attempts", "error", "updated_at"}, ...]
    }

- `counts` has exactly one key per job state: `queued`, `running`, `done`,
  `failed_model`, `failed_app`, each present even when zero.
- `jobs[].state` is the job's real state as stored in the database.

## UI (ui/status.ts)

| state          | `label()`         | `overview()` field |
| -------------- | ----------------- | ------------------ |
| `queued`       | `waiting`         | `pending`          |
| `running`      | `in progress`     | `pending`          |
| `done`         | `done`            | `done`             |
| `failed_model` | `retryable`       | `retryable`        |
| `failed_app`   | `needs attention` | `attention`        |

`overview()` also returns `total`, the sum of all counts.
`headline()` reads, for example:

    11 jobs: 3 pending, 4 done, 3 retryable, 1 need attention

Operators run `requeue` for retryable jobs; jobs that need attention need a
human to fix the input first.
''',
    'docs/decisions.md': r'''# Decision log

Newest last. A later decision supersedes an earlier one where they conflict, and
code comments older than a decision do not override it. Proposed entries are
not in force until they are marked approved.

## D-001 (2025-03-04) Offline stub model with canned responses

The pipeline talks to the summarizer only through a client with
`complete(prompt, *, key, attempt) -> str`. In this repository the client is
`StubModelClient`, which replays `<responses_dir>/<source>.json`; it never
touches the network. The model audit log (`AuditedClient`) records every call.

## D-002 (2025-04-11) One job per upload

The recorder names every upload `call-<n>.txt` and its uploader re-sends a file
when it does not see it leave the inbox in time, so the same file can arrive
more than once, also after it was processed. A source name (the file stem) is
accepted at most once: accepting a known source again returns the existing job
and removes the redelivered inbox file. It never creates a second job.

## D-003 (2025-05-20) Accepted means durable

"Accepted" means the job row is committed. Guarantees:

1. An inbox file is removed only after its job is committed. The archive copy
   the worker reads is written before the job is committed. A crash at any
   point of `accept` therefore leaves either the file in the inbox or a
   committed job, and the next `accept` run completes the hand-over.
2. `running` is a lease, not a promise. `claim` sets
   `lease_until = now + lease_seconds`. A `running` job whose lease has expired
   (`lease_until <= now`) is claimable again, exactly like a queued job (oldest
   job id first). A live lease is never taken over: its worker may still be busy.
3. Consequently the worker steps after the claim (model call, summary row,
   export row, finish) can run more than once for the same job. See D-004.

## D-004 (2025-05-20) Exactly one summary per job

Retries, re-claims and requeues must not create duplicates. A job has at most
one row in `summaries`, and Export v1 contains at most one row per job. This
applies to every code path that writes summaries or export rows.

## D-005 (2025-11-18) No salvage of malformed model output

Supersedes the 2025-06 ops request to salvage partial output. Model output that
is not valid JSON or violates docs/contracts.md is a model failure: it is
retried like a timeout and is never stored or exported. Incident 2025-11-12:
salvaged "Sure! Here is ..." text reached a customer report.

## D-006 (2026-02-02) Model failures and application failures are different

The single `failed` state is replaced by two terminal failure states:

- `failed_model`: every one of `model.max_attempts` model attempts failed
  (timeout, rate limit, outage, or output rejected under D-005). Trying again
  later can succeed.
- `failed_app`: the problem is on our side or in the input: empty transcript,
  transcript longer than `max_transcript_chars` (D-007), archive copy missing
  or unreadable. The model is not called for these jobs, and they are not
  retried; retrying cannot help until someone fixes the input.

Only model failures are retried within a run, with the configured backoff.
`jobs.attempts` counts model calls. The `error` column keeps the last error
message. Status and UI report both states separately (docs/contracts.md).
Rows still carrying the old `failed` state count as `failed_model`.

## D-007 (2026-03-09) Never truncate transcripts

The prompt builder used to cut transcripts at `max_transcript_chars`.
Incident 2026-03-02: action items at the end of long calls silently vanished.
A transcript longer than `max_transcript_chars` characters is an application
failure (`failed_app`); ops split such recordings by hand.

## D-008 (2026-03-09) Requeue only what can succeed

`requeue` moves `failed_model` jobs back to `queued` with `attempts` reset to 0.
`failed_app` jobs stay where they are. `requeue --inline` processes the requeued
jobs immediately and follows exactly the same rules as the worker (validation,
retries, failure states, D-004).

## D-009 (2026-08-21) PROPOSED, not approved: redaction of personal data

Status: proposal. Do not implement until approved.

Context: transcripts contain e-mail addresses and phone numbers of call
participants, and models echo them into action items.

Proposal:

- Redact before anything is persisted by the pipeline: archive copy, database
  rows (jobs, summaries, error texts), Export v1, status snapshot and model audit
  log. The model therefore only ever sees redacted text, and model output is
  redacted before it is stored or logged.
- E-mail addresses become `[EMAIL]`. Shape: a local part of letters, digits and
  `._%+-`, then `@`, then dot-separated labels of letters, digits and hyphens,
  ending in a top-level label of at least two letters.
- Phone numbers: left out of this proposal (false positives feared). If they are
  added, the agreed shape is `+` followed by 8-15 digits, or a national number
  `0` followed by 9-10 further digits; digits may be grouped with single spaces,
  hyphens or slashes, and the number must not touch other letters or digits.
  They become `[PHONE]`. Timestamps (`00:12:05`), dates (`2026-09-14`), ticket
  IDs (`TCK-2024-00017`) and amounts must never match.
- Status: every job in status.json gets a boolean `redacted`, true when at
  least one replacement was made in its transcript. The UI job line appends
  ` [redacted]` for such jobs. Jobs accepted before the change are `false`.
- Export v1 keeps its exact format; redacted values simply contain the tokens.
- `textutil.mask_email` is for console log lines only and is not a redaction.
''',
    'docs/operations.md': r'''# Operations

Existing originals are immutable: `fixtures/original.txt` must never change.
Work only inside this project. Everything here runs offline.

## Workspace layout

A workspace is the directory holding the config file; relative paths in the
config resolve against it (see `config/pipeline.json` for the defaults).

| Path (default)          | Written by        | Purpose                                  |
| ----------------------- | ----------------- | ---------------------------------------- |
| `inbox/`                | recorder uploader | new transcripts, `call-<n>.txt`          |
| `archive/`              | ingest            | archive copy of every accepted transcript |
| `state/pipeline.db`     | all commands      | jobs and summaries (SQLite)              |
| `state/model_calls.jsonl` | worker/requeue  | model audit log                          |
| `out/summaries_v1.tsv`  | worker/requeue    | Export v1 for the reporting team         |
| `out/status.json`       | worker/status     | status snapshot for the ops UI           |

## Commands

    python3 -m pipeline.cli --config <cfg> accept
    python3 -m pipeline.cli --config <cfg> work [--max-jobs N]
    python3 -m pipeline.cli --config <cfg> requeue [--inline]
    python3 -m pipeline.cli --config <cfg> status
    python3 -m pipeline.cli --config <cfg> export --rebuild
    node ui/render.ts out/status.json

Every command accepts `--now <epoch seconds>` to pin the clock. On the worker
host a systemd timer runs `accept` and then `work` every 30 seconds.

## Crash rehearsal

Set `PIPELINE_CRASH_AT=<checkpoint>` (names in `pipeline/faults.py`) and run a
command; the process dies at that point with exit status 75, as in a power cut.
Then run the same commands again with a later `--now`: the guarantees in
docs/decisions.md (D-002 to D-004) must hold. `scripts/rehearse_crash.sh` walks
through all checkpoints.

## Model audit log

One JSON line per model call with `key`, `attempt`, `model`, `prompt`,
`outcome` and, for answered calls, `response`. Kept for audit: do not drop
fields. Counting lines per `key` is how ops check model quota use.

## Schema changes

Additive only, applied automatically by `Store.migrate()` whenever a database is
opened. The production database is never rebuilt and old rows must keep working.

## Export v1

Imported nightly by the reporting team's importer. The format is frozen; see
docs/contracts.md. `export --rebuild` regenerates it from the database.

## Incident notes (unsorted, as reported)

- 2026-08-14: The reporting team saw call-0388 twice in the morning import,
  same title both times. The worker host had been rebooted overnight.
- 2026-08-30: call-0402 was uploaded on Friday (uploader log: file left the
  inbox at 17:02). The worker host was patched and rebooted Friday evening. On
  Monday there was no summary, no failure, and the status page showed nothing
  unusual.
- 2026-09-02: A summary titled "Summary" whose only bullet began "Sure! Here is
  the summary you asked for" appeared in the customer report. It came from the
  inline requeue we ran during the provider outage.
- 2026-09-05: The status page showed 2 pending for three days. Nobody noticed.
- 2026-09-10: call-0409 (recorder produced an empty transcript) was requeued
  four times and used model quota every time.
- 2026-09-11: The uploader retried call-0410 after a network timeout. Two jobs,
  two rows in the export.
- 2026-09-19: Long workshop call-0415: the summary has no action items although
  the last 20 minutes were only action items.
''',
    'fixtures/responses/call-0412.json': r'''{
  "default": {
    "kind": "ok",
    "text": "{\"title\": \"Weekly delivery sync (Rhine)\", \"bullets\": [\"Ingestion rewrite merged, load tests green\", \"Steering meeting moved to Thursday 14:00\", \"Q4 budget confirmed at Q3 level\", \"Vendor API v2 deprecated end of November\"], \"action_items\": [{\"owner\": \"Tomas\", \"task\": \"Plan the API v3 migration next sprint\"}, {\"owner\": \"Priya\", \"task\": \"Prepare the updated cost sheet before Thursday\"}]}"
  }
}
''',
    'fixtures/transcripts/call-0412.txt': r'''[00:00:03] Lea: Morning all, this is the weekly delivery sync for the Rhine project.
[00:00:11] Tomas: Quick status: the ingestion rewrite is merged, load tests are green.
[00:01:02] Lea: Good. The steering meeting moved to Thursday, 14:00.
[00:01:40] Priya: Budget for Q4 is confirmed at the same level as Q3.
[00:02:15] Tomas: One risk: the vendor API deprecates v2 at the end of November.
[00:02:58] Lea: Then we plan the migration in the next sprint. Tomas owns it.
[00:03:30] Priya: I will prepare the updated cost sheet before Thursday.
[00:03:52] Lea: Thanks, that's it for today.
''',
    'pipeline/__init__.py': r'''"""Offline transcript-to-summary pipeline.

Transcripts dropped into the inbox are accepted as jobs (ingest), summarised by
the worker through a model client, validated against the output contract,
stored in SQLite and appended to the Export v1 file for the reporting team.

See README.md for the layout and docs/decisions.md for the guarantees.
"""
__version__ = '1.7.2'
''',
    'pipeline/cli.py': r'''"""Command line: python3 -m pipeline.cli [--config CFG] <command> [options].

    accept              accept every transcript waiting in the inbox
    work                process claimable jobs until none is left
    requeue [--inline]  put failed jobs back into the queue (and process them now)
    status              write and print the status snapshot
    export --rebuild    rewrite Export v1 from the database

--now <epoch seconds> pins the clock (crash rehearsals, tests).
"""
from __future__ import annotations

import argparse
import json
import sys
import time

from . import config, export, ingest, status
from .requeue import requeue
from .store import Store
from .worker import Worker


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog='pipeline', description=__doc__.splitlines()[0])
    ap.add_argument('--config', default='config/pipeline.json')
    sub = ap.add_subparsers(dest='command', required=True)
    for name in ('accept', 'work', 'requeue', 'status', 'export'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--now', type=int)
        if name == 'work':
            cmd.add_argument('--max-jobs', type=int)
        if name == 'requeue':
            cmd.add_argument('--inline', action='store_true')
        if name == 'export':
            cmd.add_argument('--rebuild', action='store_true')
    return ap


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    cfg = config.load(args.config)
    now = args.now if args.now is not None else int(time.time())
    store = Store(cfg.db_path)
    try:
        if args.command == 'accept':
            ingest.accept_all(cfg, store, now)
        elif args.command == 'work':
            Worker(cfg, store).run(now, max_jobs=args.max_jobs)
        elif args.command == 'requeue':
            requeue(cfg, store, now, inline=args.inline)
        elif args.command == 'status':
            snap = status.snapshot(store, now)
            status.write(cfg.status_path, snap)
            print(json.dumps(snap, indent=2, sort_keys=True))
        elif args.command == 'export':
            if not args.rebuild:
                print('nothing to do: export rows are written by the worker; use --rebuild',
                      file=sys.stderr)
                return 2
            print(f'{export.rebuild(cfg.export_path, store)} rows written')
    finally:
        store.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
''',
    'pipeline/config.py': r'''"""Configuration loading.

Relative paths in the config file resolve against the directory that contains
the config file (the "workspace"). Unknown keys are ignored so that older
config files keep working after upgrades.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULTS = {
    'db_path': 'state/pipeline.db',
    'inbox_dir': 'inbox',
    'archive_dir': 'archive',
    'export_path': 'out/summaries_v1.tsv',
    'status_path': 'out/status.json',
    'calls_log': 'state/model_calls.jsonl',
    'responses_dir': 'fixtures/responses',
    'lease_seconds': 300,
    'max_transcript_chars': 20000,
    'model': {
        'name': 'stub-summarizer-2',
        'max_attempts': 3,
        'backoff_seconds': [2, 10, 30],
    },
}

PATH_KEYS = ('db_path', 'inbox_dir', 'archive_dir', 'export_path', 'status_path',
             'calls_log', 'responses_dir')


@dataclass
class Config:
    root: Path
    db_path: Path
    inbox_dir: Path
    archive_dir: Path
    export_path: Path
    status_path: Path
    calls_log: Path
    responses_dir: Path
    lease_seconds: int
    max_transcript_chars: int
    model_name: str
    max_attempts: int
    backoff_seconds: list = field(default_factory=list)

    def backoff(self, attempt: int) -> float:
        """Seconds to wait after failed model attempt number `attempt` (1-based)."""
        if not self.backoff_seconds or attempt < 1:
            return 0
        return self.backoff_seconds[min(attempt, len(self.backoff_seconds)) - 1]


def _merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load(path) -> Config:
    path = Path(path).resolve()
    raw = _merge(DEFAULTS, json.loads(path.read_text(encoding='utf-8')))
    root = path.parent

    def resolve(key):
        value = Path(raw[key])
        return value if value.is_absolute() else root / value

    paths = {key: resolve(key) for key in PATH_KEYS}
    model = raw['model']
    if int(model['max_attempts']) < 1:
        raise ValueError('model.max_attempts must be >= 1')
    return Config(root=root, lease_seconds=int(raw['lease_seconds']),
                  max_transcript_chars=int(raw['max_transcript_chars']),
                  model_name=str(model['name']), max_attempts=int(model['max_attempts']),
                  backoff_seconds=list(model.get('backoff_seconds', [])), **paths)
''',
    'pipeline/errors.py': r'''"""Exception hierarchy.

ModelError and its subclasses describe problems with the model call or its
output. TranscriptError describes problems with our input. Everything else is
a bug or an environment problem.
"""


class PipelineError(Exception):
    """Base class for expected pipeline failures."""


class ModelError(PipelineError):
    """The model call failed or returned unusable output."""


class ModelTimeout(ModelError):
    """The provider did not answer in time."""


class ModelRateLimited(ModelError):
    """The provider rejected the call with a rate limit."""


class ModelUnavailable(ModelError):
    """The provider (or the stub's canned response) is not available."""


class ModelOutputError(ModelError):
    """The output is not JSON or violates docs/contracts.md."""


class TranscriptError(PipelineError):
    """The transcript cannot be summarised as it is (empty, too long, unreadable)."""
''',
    'pipeline/export.py': r'''"""Export v1: the TSV file the downstream reporting team imports.

The format is frozen (docs/contracts.md, "Export v1"):

    header  job_id, source, title, bullets, action_items, model
    bullets joined with " | "; action items as "owner: task" joined with " | "
    UTF-8, "\\n" line endings, tabs/newlines inside values collapsed to one space
"""
from __future__ import annotations

from pathlib import Path

from .textutil import one_line

HEADER = ('job_id', 'source', 'title', 'bullets', 'action_items', 'model')
JOIN = ' | '


def row(job: dict, summary: dict, model: str) -> tuple:
    actions = JOIN.join(f"{i['owner']}: {i['task']}" for i in summary['action_items'])
    return (job['id'], job['source'], summary['title'], JOIN.join(summary['bullets']),
            actions, model)


def format_row(values) -> str:
    return '\t'.join(one_line(v) for v in values) + '\n'


def append_row(path: Path, job: dict, summary: dict, model: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open('a', encoding='utf-8', newline='') as fh:
        if new:
            fh.write(format_row(HEADER))
        fh.write(format_row(row(job, summary, model)))


def rebuild(path: Path, store) -> int:
    """Rewrite the whole export from the summaries table (ops, after DB repairs)."""
    lines = [format_row(HEADER)]
    for s in store.summaries():
        job = {'id': s['job_id'], 'source': s['source']}
        lines.append(format_row(row(job, s['body'], s['model'])))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(''.join(lines), encoding='utf-8', newline='')
    tmp.replace(path)
    return len(lines) - 1


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding='utf-8').splitlines()
    header = lines[0].split('\t')
    return [dict(zip(header, line.split('\t'))) for line in lines[1:] if line]
''',
    'pipeline/faults.py': r'''"""Crash rehearsal hooks (docs/operations.md, "Crash rehearsal").

Set PIPELINE_CRASH_AT=<checkpoint> and the process exits immediately with
status 75 when it reaches that checkpoint: no cleanup, no exception handlers,
no flushing of anything that was not already written -- like a power cut.

Checkpoints in use (keep these names, ops scripts depend on them):

    ingest:  after_archive
    worker:  after_claim, after_model, after_summary, after_export
"""
import os

CRASH_EXIT = 75
CHECKPOINTS = ('after_archive', 'after_claim', 'after_model', 'after_summary', 'after_export')


def checkpoint(name: str) -> None:
    if name not in CHECKPOINTS:
        raise ValueError(f'unknown checkpoint {name!r}')
    if os.environ.get('PIPELINE_CRASH_AT') == name:
        os._exit(CRASH_EXIT)
''',
    'pipeline/ingest.py': r'''"""Accept transcripts dropped into the inbox by the recorder's uploader.

The uploader writes `<inbox>/call-<n>.txt` and considers the upload delivered
once the file disappears from the inbox.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from . import faults

SUFFIX = '.txt'


def pending(cfg) -> list[Path]:
    """Inbox files ready for acceptance, oldest name first."""
    if not cfg.inbox_dir.is_dir():
        return []
    return sorted(p for p in cfg.inbox_dir.iterdir()
                  if p.is_file() and p.suffix == SUFFIX and not p.name.startswith('.'))


def accept_file(cfg, store, path: Path, now: int) -> int:
    source = path.stem
    cfg.archive_dir.mkdir(parents=True, exist_ok=True)
    target = cfg.archive_dir / path.name
    # Move first: once the file is out of the inbox nobody can accept it twice.
    shutil.move(str(path), target)
    faults.checkpoint('after_archive')
    return store.add_job(source, target, now)


def accept_all(cfg, store, now: int, log=print) -> list[int]:
    accepted = []
    for path in pending(cfg):
        job_id = accept_file(cfg, store, path, now)
        log(f'accepted {path.name} as job {job_id}')
        accepted.append(job_id)
    return accepted
''',
    'pipeline/legacy_batch.py': r'''"""DEPRECATED (2025-10): synchronous batch summariser from before the job queue.

Not wired into the CLI. Kept only because the 2025 backfill notebook imports
`summarise_directory`. It bypasses the job table entirely and must not be
used for new work; the worker is the supported path.
"""
from __future__ import annotations

import json
from pathlib import Path

from .output import salvage_summary
from .textutil import read_text

LEGACY_MAX_CHARS = 12000


def summarise_directory(directory, client, out_path) -> int:
    """Summarise every *.txt in `directory` into a JSON-lines file.

    Each transcript is sent once; there are no retries and no job records.
    """
    directory = Path(directory)
    count = 0
    with Path(out_path).open('a', encoding='utf-8') as out:
        for path in sorted(directory.glob('*.txt')):
            prompt = output.build_prompt(read_text(path), LEGACY_MAX_CHARS)
            raw = client.complete(prompt, key=path.stem, attempt=1)
            summary = salvage_summary(raw)
            out.write(json.dumps({'source': path.stem, 'summary': summary}) + '\n')
            count += 1
    return count
''',
    'pipeline/model_client.py': r'''"""Model clients.

StubModelClient is the only model client in this repository. It replays canned
responses from <responses_dir>/<source>.json so every run is deterministic and
offline. Response file format:

    {"attempts": [<response>, ...], "default": <response>}

Model attempt N (1-based) uses attempts[N-1] when present, otherwise "default".
A <response> is one of

    {"kind": "ok", "text": "..."}     the model answered (the text may be garbage)
    {"kind": "timeout"}                the provider timed out
    {"kind": "rate_limited"}           the provider answered 429

A missing file or entry behaves like a provider outage (ModelUnavailable).

AuditedClient wraps a client and appends one JSON line per call to the model
audit log (docs/operations.md, "Model audit log").
"""
from __future__ import annotations

import json
from pathlib import Path

from .errors import ModelRateLimited, ModelTimeout, ModelUnavailable


class StubModelClient:
    def __init__(self, responses_dir, name: str = 'stub-summarizer-2'):
        self.responses_dir = Path(responses_dir)
        self.name = name

    def _response(self, key: str, attempt: int):
        path = self.responses_dir / f'{key}.json'
        if not path.is_file():
            return None
        spec = json.loads(path.read_text(encoding='utf-8'))
        sequence = spec.get('attempts') or []
        if 1 <= attempt <= len(sequence):
            return sequence[attempt - 1]
        return spec.get('default')

    def complete(self, prompt: str, *, key: str, attempt: int) -> str:
        response = self._response(key, attempt)
        if response is None:
            raise ModelUnavailable(f'no canned response for {key}')
        kind = response.get('kind')
        if kind == 'timeout':
            raise ModelTimeout(f'{self.name} did not answer in time')
        if kind == 'rate_limited':
            raise ModelRateLimited(f'{self.name} answered 429')
        if kind == 'ok':
            return str(response.get('text', ''))
        raise ModelUnavailable(f'unknown canned response kind {kind!r}')


class AuditedClient:
    """Records every call: key, attempt, model, prompt, outcome and response."""

    def __init__(self, inner, log_path):
        self.inner = inner
        self.log_path = Path(log_path)

    @property
    def name(self) -> str:
        return self.inner.name

    def complete(self, prompt: str, *, key: str, attempt: int) -> str:
        entry = {'key': key, 'attempt': attempt, 'model': self.name, 'prompt': prompt}
        try:
            text = self.inner.complete(prompt, key=key, attempt=attempt)
        except Exception as exc:
            entry['outcome'] = type(exc).__name__
            self._write(entry)
            raise
        entry['outcome'] = 'ok'
        entry['response'] = text
        self._write(entry)
        return text

    def _write(self, entry: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(entry, sort_keys=True) + '\n')


def make_client(cfg):
    return AuditedClient(StubModelClient(cfg.responses_dir, cfg.model_name), cfg.calls_log)
''',
    'pipeline/output.py': r'''"""Prompt and structured-output contract (docs/contracts.md)."""
from __future__ import annotations

import json
import re

from .errors import ModelOutputError

MAX_TITLE = 120
MAX_BULLETS = 8
_FENCE = re.compile(r'^```(?:json)?\s*(.*?)\s*```$', re.S)

INSTRUCTIONS = """You summarise recorded business calls.
Return ONLY a JSON object with these keys:
  "title": string, at most 120 characters
  "bullets": list of 1 to 8 short strings
  "action_items": list of {"owner": string, "task": string} (may be empty)
Do not add commentary before or after the JSON.
"""

SEPARATOR = '---'


def build_prompt(transcript: str, max_chars: int) -> str:
    body = transcript.strip('﻿')
    if len(body) > max_chars:
        # keep the call inside the model's context budget
        body = body[:max_chars]
    return f'{INSTRUCTIONS}\n{SEPARATOR}\n{body}\n{SEPARATOR}\n'


def _strip_fence(raw: str) -> str:
    text = str(raw).strip()
    match = _FENCE.match(text)
    return match.group(1) if match else text


def validate(data) -> list[str]:
    """Return a list of contract violations (empty when the summary is valid)."""
    if not isinstance(data, dict):
        return ['top level must be a JSON object']
    problems = []
    title = data.get('title')
    if not isinstance(title, str) or not title.strip():
        problems.append('title must be a non-empty string')
    elif len(title.strip()) > MAX_TITLE:
        problems.append(f'title longer than {MAX_TITLE} characters')
    bullets = data.get('bullets')
    if (not isinstance(bullets, list) or not 1 <= len(bullets) <= MAX_BULLETS
            or not all(isinstance(b, str) and b.strip() for b in bullets)):
        problems.append(f'bullets must be 1-{MAX_BULLETS} non-empty strings')
    items = data.get('action_items', [])
    if not isinstance(items, list) or not all(
            isinstance(i, dict) and isinstance(i.get('owner'), str)
            and isinstance(i.get('task'), str) and i['task'].strip() for i in items):
        problems.append('action_items must be a list of {owner, task} strings')
    return problems


def normalize(data: dict) -> dict:
    return {
        'title': data['title'].strip(),
        'bullets': [b.strip() for b in data['bullets']],
        'action_items': [{'owner': i['owner'].strip(), 'task': i['task'].strip()}
                         for i in data.get('action_items', [])],
    }


def parse_summary(raw: str) -> dict:
    """Strict parser: returns a normalised summary or raises ModelOutputError."""
    try:
        data = json.loads(_strip_fence(raw))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ModelOutputError(f'output is not JSON ({exc.__class__.__name__})') from None
    problems = validate(data)
    if problems:
        raise ModelOutputError('; '.join(problems))
    return normalize(data)


def salvage_summary(raw: str) -> dict:
    """Best-effort summary from whatever the model said (ops request, 2025-06).

    Never raises: unusable output becomes a one-bullet summary carrying the raw
    text, so the export row is never empty during an incident.
    """
    try:
        return parse_summary(raw)
    except ModelOutputError:
        text = ' '.join(str(raw).split())
        return {'title': 'Summary', 'bullets': [text[:500] or '(empty)'], 'action_items': []}
''',
    'pipeline/requeue.py': r'''"""Put failed jobs back into the queue (ops runbook, "Requeue").

requeue() moves failed jobs back to `queued` and resets their attempts.
With inline=True the jobs are processed right away in this process; ops use
that during incidents while the worker service is stopped.
"""
from __future__ import annotations

from pathlib import Path

from . import export
from .errors import ModelError
from .model_client import make_client
from .output import salvage_summary
from .textutil import read_text


def requeue(cfg, store, now: int, inline: bool = False, client=None, log=print) -> list[int]:
    ids = [job['id'] for job in store.jobs('failed')]
    for job_id in ids:
        store.requeue(job_id, now)
        log(f'requeued job {job_id}')
    if inline and ids:
        client = client or make_client(cfg)
        for job_id in ids:
            _process_inline(cfg, store, client, store.job(job_id), now, log)
    return ids


def _process_inline(cfg, store, client, job: dict, now: int, log) -> bool:
    text = read_text(Path(job['transcript_path']))
    prompt = output.build_prompt(text, cfg.max_transcript_chars)
    for attempt in range(1, cfg.max_attempts + 1):
        store.bump_attempt(job['id'])
        try:
            raw = client.complete(prompt, key=job['source'], attempt=attempt)
        except ModelError as exc:
            log(f"inline job {job['id']} attempt {attempt}: {exc}")
            continue
        # During an outage ops prefer a partial summary over none (2025-06).
        summary = salvage_summary(raw)
        store.save_summary(job['id'], summary, client.name, now)
        export.append_row(cfg.export_path, job, summary, client.name)
        store.finish(job['id'], now)
        log(f"inline job {job['id']} done")
        return True
    store.fail(job['id'], 'failed', 'model failed during inline requeue', now)
    return False
''',
    'pipeline/status.py': r'''"""Status snapshot for the ops UI (docs/contracts.md).

The worker rewrites out/status.json after every run; `cli status` writes and
prints it on demand. ui/status.ts renders it.
"""
from __future__ import annotations

import json
from pathlib import Path

# States the status page understands. Anything else is shown as failed.
UI_STATES = ('queued', 'running', 'done', 'failed')


def _ui_state(state: str) -> str:
    return state if state in UI_STATES else 'failed'


def snapshot(store, now: int) -> dict:
    counts = {state: 0 for state in UI_STATES}
    for state, n in store.count_by_state().items():
        counts[_ui_state(state)] += n
    jobs = [{
        'id': j['id'],
        'source': j['source'],
        'state': _ui_state(j['state']),
        'attempts': j['attempts'],
        'error': j['error'],
        'updated_at': j['updated_at'],
    } for j in store.jobs()]
    return {'generated_at': now, 'counts': counts, 'jobs': jobs}


def write(path: Path, snap: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(snap, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)
''',
    'pipeline/store.py': r'''"""SQLite persistence for jobs and summaries.

Job lifecycle (docs/decisions.md):  queued -> running -> done | failed
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

STATES = ('queued', 'running', 'done', 'failed')
SCHEMA = """
-- Pipeline schema. Changes must be additive (docs/operations.md, "Schema changes").
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,             -- inbox file stem, e.g. call-0412
  transcript_path TEXT NOT NULL,    -- archive copy the worker reads
  state TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  lease_until INTEGER,              -- epoch seconds, only meaningful while running
  error TEXT,
  accepted_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS jobs_source ON jobs(source);

CREATE TABLE IF NOT EXISTS summaries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id),
  title TEXT NOT NULL,
  body TEXT NOT NULL,               -- normalised summary JSON (docs/contracts.md)
  model TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS summaries_job ON summaries(job_id);

CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT
);
"""
SCHEMA_VERSION = '3'


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.migrate()

    def migrate(self) -> None:
        """Bring any older database up to date. Additive changes only."""
        self.db.executescript(SCHEMA)
        self.db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                        (SCHEMA_VERSION,))
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    # -- jobs -------------------------------------------------------------
    def add_job(self, source: str, transcript_path, now: int) -> int:
        cur = self.db.execute(
            'INSERT INTO jobs(source, transcript_path, state, accepted_at, updated_at) '
            "VALUES(?, ?, 'queued', ?, ?)", (source, str(transcript_path), now, now))
        self.db.commit()
        return cur.lastrowid

    def job(self, job_id: int):
        row = self.db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
        return dict(row) if row else None

    def find_by_source(self, source: str):
        row = self.db.execute('SELECT * FROM jobs WHERE source = ? ORDER BY id LIMIT 1',
                              (source,)).fetchone()
        return dict(row) if row else None

    def jobs(self, state: str | None = None) -> list[dict]:
        if state is None:
            rows = self.db.execute('SELECT * FROM jobs ORDER BY id')
        else:
            rows = self.db.execute('SELECT * FROM jobs WHERE state = ? ORDER BY id', (state,))
        return [dict(r) for r in rows]

    def claim(self, now: int, lease_seconds: int):
        """Lease the oldest queued job to the caller."""
        row = self.db.execute(
            "SELECT id FROM jobs WHERE state = 'queued' ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return None
        self.db.execute(
            "UPDATE jobs SET state = 'running', lease_until = ?, updated_at = ? WHERE id = ?",
            (now + lease_seconds, now, row['id']))
        self.db.commit()
        return self.job(row['id'])

    def bump_attempt(self, job_id: int) -> int:
        self.db.execute('UPDATE jobs SET attempts = attempts + 1 WHERE id = ?', (job_id,))
        self.db.commit()
        return self.job(job_id)['attempts']

    def finish(self, job_id: int, now: int) -> None:
        self.db.execute(
            "UPDATE jobs SET state = 'done', lease_until = NULL, error = NULL, updated_at = ? "
            'WHERE id = ?', (now, job_id))
        self.db.commit()

    def fail(self, job_id: int, state: str, error: str, now: int) -> None:
        self.db.execute(
            'UPDATE jobs SET state = ?, lease_until = NULL, error = ?, updated_at = ? WHERE id = ?',
            (state, error, now, job_id))
        self.db.commit()

    def requeue(self, job_id: int, now: int) -> None:
        self.db.execute(
            "UPDATE jobs SET state = 'queued', attempts = 0, error = NULL, lease_until = NULL, "
            'updated_at = ? WHERE id = ?', (now, job_id))
        self.db.commit()

    def count_by_state(self) -> dict:
        return {r['state']: r['n'] for r in
                self.db.execute('SELECT state, COUNT(*) AS n FROM jobs GROUP BY state')}

    # -- summaries ----------------------------------------------------------
    def save_summary(self, job_id: int, summary: dict, model: str, now: int) -> None:
        self.db.execute(
            'INSERT INTO summaries(job_id, title, body, model, created_at) VALUES(?, ?, ?, ?, ?)',
            (job_id, summary['title'], json.dumps(summary, sort_keys=True), model, now))
        self.db.commit()

    def summaries(self, job_id: int | None = None) -> list[dict]:
        sql = ('SELECT s.*, j.source FROM summaries s JOIN jobs j ON j.id = s.job_id')
        if job_id is None:
            rows = self.db.execute(sql + ' ORDER BY s.id')
        else:
            rows = self.db.execute(sql + ' WHERE s.job_id = ? ORDER BY s.id', (job_id,))
        out = []
        for r in rows:
            d = dict(r)
            d['body'] = json.loads(d['body'])
            out.append(d)
        return out
''',
    'pipeline/textutil.py': r'''"""Small text helpers shared by ingest, worker and export."""
import re

_EMAIL_FOR_LOGS = re.compile(r'([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+)')


def mask_email(text: str) -> str:
    """Shorten e-mail addresses in *log output* to j***@example.org.

    This is a readability aid for console logs, not a redaction: the first
    letter and the domain stay visible. See D-009 in docs/decisions.md.
    """
    return _EMAIL_FOR_LOGS.sub(lambda m: f'{m.group(1)}***@{m.group(2)}', text)


def one_line(value) -> str:
    """Collapse tabs, newlines and repeated blanks so a value fits one TSV cell."""
    return ' '.join(str(value).split())


def preview(text: str, limit: int = 60) -> str:
    text = one_line(text)
    return text if len(text) <= limit else text[:limit - 3] + '...'


def read_text(path) -> str:
    """Read a transcript. Recorder output is UTF-8, older uploads were cp1252."""
    data = path.read_bytes()
    try:
        return data.decode('utf-8')
    except UnicodeDecodeError:
        return data.decode('cp1252')
''',
    'pipeline/worker.py': r'''"""The worker: claims jobs and turns transcripts into validated summaries.

One job, step by step:

    claim -> read archived transcript -> model call (with retries)
          -> parse/validate -> summary row -> export row -> done
"""
from __future__ import annotations

import time
from pathlib import Path

from . import export, faults, output, status
from .model_client import make_client
from .textutil import mask_email, preview, read_text


class Worker:
    def __init__(self, cfg, store, client=None, sleep=time.sleep, log=print):
        self.cfg = cfg
        self.store = store
        self.client = client or make_client(cfg)
        self.sleep = sleep
        self.log = log

    def run(self, now: int, max_jobs: int | None = None) -> list[tuple[int, str]]:
        """Process claimable jobs until none is left (or max_jobs is reached)."""
        results = []
        while max_jobs is None or len(results) < max_jobs:
            job = self.store.claim(now, self.cfg.lease_seconds)
            if job is None:
                break
            faults.checkpoint('after_claim')
            results.append((job['id'], self.process(job, now)))
        status.write(self.cfg.status_path, status.snapshot(self.store, now))
        return results

    def process(self, job: dict, now: int) -> str:
        while True:
            attempt = self.store.bump_attempt(job['id'])
            try:
                text = read_text(Path(job['transcript_path']))
                prompt = output.build_prompt(text, self.cfg.max_transcript_chars)
                raw = self.client.complete(prompt, key=job['source'], attempt=attempt)
                faults.checkpoint('after_model')
                summary = output.parse_summary(raw)
                self.store.save_summary(job['id'], summary, self.client.name, now)
                faults.checkpoint('after_summary')
                export.append_row(self.cfg.export_path, job, summary, self.client.name)
                faults.checkpoint('after_export')
                self.store.finish(job['id'], now)
                self.log(f"job {job['id']} ({job['source']}) done: {preview(summary['title'])}")
                return 'done'
            except Exception as exc:
                message = f'{type(exc).__name__}: {exc}'
                self.log(f"job {job['id']} attempt {attempt} failed: {mask_email(message)}")
                if attempt >= self.cfg.max_attempts:
                    self.store.fail(job['id'], 'failed', message, now)
                    return 'failed'
                self.sleep(self.cfg.backoff(attempt))
''',
    'scripts/rehearse_crash.sh': r'''#!/usr/bin/env bash
# Crash rehearsal (docs/operations.md). Copies the fixture transcripts into a
# scratch workspace, kills the pipeline at every checkpoint in turn, restarts
# it after the lease has expired and prints the resulting job table and export.
# Usage: scripts/rehearse_crash.sh [scratch-dir]
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
scratch="${1:-$(mktemp -d)}"
lease=300
for step in after_archive after_claim after_model after_summary after_export; do
  ws="$scratch/$step"
  rm -rf "$ws"; mkdir -p "$ws/inbox"
  cp "$repo"/fixtures/transcripts/*.txt "$ws/inbox/"
  printf '{"responses_dir": "%s", "model": {"backoff_seconds": [0]}}\n' \
    "$repo/fixtures/responses" > "$ws/pipeline.json"
  run() { (cd "$repo" && python3 -m pipeline.cli --config "$ws/pipeline.json" "$@"); }
  t=1000
  PIPELINE_CRASH_AT="$step" run accept --now "$t" || echo "[$step] accept exited $?"
  run accept --now "$t"
  PIPELINE_CRASH_AT="$step" run work --now "$t" || echo "[$step] work exited $?"
  run work --now $((t + lease + 1))
  echo "== $step"
  python3 - "$ws" <<'PY'
import sqlite3, sys
from pathlib import Path
ws = Path(sys.argv[1])
db = sqlite3.connect(ws / 'state/pipeline.db')
for row in db.execute('SELECT j.id, j.source, j.state, COUNT(s.id) FROM jobs j '
                      'LEFT JOIN summaries s ON s.job_id = j.id GROUP BY j.id'):
    print('  job', *row)
export = ws / 'out/summaries_v1.tsv'
if export.exists():
    print('  export rows:', len(export.read_text().splitlines()) - 1)
PY
done
''',
    'ui/package.json': r'''{"type": "module", "private": true}
''',
    'ui/render.ts': r'''// Usage: node ui/render.ts [out/status.json]
import { readFileSync } from 'node:fs';
import { parseSnapshot, render } from './status.ts';

const path = process.argv[2] ?? 'out/status.json';
console.log(render(parseSnapshot(readFileSync(path, 'utf8'))));
''',
    'ui/status.ts': r'''// Ops status page model: reads out/status.json (docs/contracts.md).
// Runtime: node with type stripping (no tsc build step; erasable TypeScript only).

export function padLeft(value: string | number, width: number): string {
  const s = String(value);
  return s.length >= width ? s : ' '.repeat(width - s.length) + s;
}

export function padRight(value: string, width: number): string {
  return value.length >= width ? value : value + ' '.repeat(width - value.length);
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

export function age(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '?';
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

export interface JobRow {
  id: number;
  source: string;
  state: string;
  attempts: number;
  error: string | null;
  updated_at: number;
}

export interface Snapshot {
  generated_at: number;
  counts: Record<string, number>;
  jobs: JobRow[];
}

export interface Overview {
  total: number;
  pending: number;
  done: number;
  failed: number;
}

const LABELS: Record<string, string> = {
  queued: 'waiting',
  running: 'in progress',
  done: 'done',
  failed: 'FAILED',
};

export function label(state: string): string {
  return LABELS[state] ?? 'FAILED';
}

export function parseSnapshot(text: string): Snapshot {
  const s = JSON.parse(text);
  if (!s || typeof s !== 'object' || typeof s.counts !== 'object' || s.counts === null) {
    throw new Error('not a status snapshot');
  }
  s.jobs ??= [];
  return s as Snapshot;
}

export function overview(s: Snapshot): Overview {
  const c = s.counts ?? {};
  const n = (k: string): number => c[k] ?? 0;
  const total = Object.values(c).reduce((a, b) => a + b, 0);
  return { total, pending: n('queued') + n('running'), done: n('done'), failed: n('failed') };
}

export function headline(s: Snapshot): string {
  const o = overview(s);
  return `${plural(o.total, 'job')}: ${o.pending} pending, ${o.done} done, ${o.failed} failed`;
}

export function jobLine(j: JobRow, now?: number): string {
  let line = `${padLeft(j.id, 5)}  ${padRight(j.source, 14)} ${label(j.state)}`;
  if (j.attempts > 0) line += ` (${plural(j.attempts, 'attempt')})`;
  if (now !== undefined) line += `, ${age(now - j.updated_at)} ago`;
  return line;
}

export function render(s: Snapshot): string {
  const lines = [headline(s)];
  for (const j of s.jobs) lines.push(jobLine(j, s.generated_at));
  return lines.join('\n');
}
''',
}

VISIBLE = r'''import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from pipeline import config, export
from pipeline.errors import ModelOutputError
from pipeline.output import parse_summary

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / 'fixtures'


def make_workspace(tmp):
    ws = Path(tmp) / 'ws'
    (ws / 'inbox').mkdir(parents=True)
    cfg = {'responses_dir': str(FIXTURES / 'responses'), 'model': {'backoff_seconds': [0, 0, 0]}}
    (ws / 'pipeline.json').write_text(json.dumps(cfg))
    return ws


def drop_fixture(ws, name):
    text = (FIXTURES / 'transcripts' / f'{name}.txt').read_text(encoding='utf-8')
    (ws / 'inbox' / f'{name}.txt').write_text(text, encoding='utf-8')


def cli(ws, *args, crash=None):
    env = dict(os.environ)
    env.pop('PIPELINE_CRASH_AT', None)
    if crash:
        env['PIPELINE_CRASH_AT'] = crash
    return subprocess.run([sys.executable, '-m', 'pipeline.cli', '--config', str(ws / 'pipeline.json'),
                           *args], cwd=REPO, env=env, capture_output=True, text=True, timeout=60)


def query(ws, sql):
    db = sqlite3.connect(ws / 'state' / 'pipeline.db')
    try:
        return db.execute(sql).fetchall()
    finally:
        db.close()


class EndToEnd(unittest.TestCase):
    def test_accept_and_work_happy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = make_workspace(tmp)
            drop_fixture(ws, 'call-0412')
            p = cli(ws, 'accept', '--now', '1000')
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(list((ws / 'inbox').iterdir()), [])
            p = cli(ws, 'work', '--now', '1000')
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(query(ws, 'SELECT source, state FROM jobs'), [('call-0412', 'done')])
            self.assertEqual(query(ws, 'SELECT title FROM summaries'), [('Weekly delivery sync (Rhine)',)])
            lines = (ws / 'out' / 'summaries_v1.tsv').read_text(encoding='utf-8').splitlines()
            self.assertEqual(lines[0], 'job_id\tsource\ttitle\tbullets\taction_items\tmodel')
            self.assertEqual(lines[1].split('\t')[:3], ['1', 'call-0412', 'Weekly delivery sync (Rhine)'])
            snap = json.loads((ws / 'out' / 'status.json').read_text())
            self.assertEqual(snap['counts']['done'], 1)

    def test_transient_model_errors_are_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = make_workspace(tmp)
            responses = Path(tmp) / 'responses'
            responses.mkdir()
            summary = {'title': 'Release checklist', 'bullets': ['Ship Tuesday if QA signs off'],
                       'action_items': [{'owner': 'Ines', 'task': 'Chase QA tomorrow'}]}
            (responses / 'call-0413.json').write_text(json.dumps({
                'attempts': [{'kind': 'timeout'},
                             {'kind': 'ok', 'text': 'Sure! Here is the summary you asked for.'}],
                'default': {'kind': 'ok', 'text': '```json\n' + json.dumps(summary) + '\n```'}}))
            cfg = json.loads((ws / 'pipeline.json').read_text())
            cfg['responses_dir'] = str(responses)
            (ws / 'pipeline.json').write_text(json.dumps(cfg))
            (ws / 'inbox' / 'call-0413.txt').write_text('[00:00:02] Sam: Only the release checklist today.\n')
            cli(ws, 'accept', '--now', '1000')
            p = cli(ws, 'work', '--now', '1000')
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(query(ws, 'SELECT state FROM jobs'), [('done',)])
            self.assertEqual(query(ws, 'SELECT title FROM summaries'), [('Release checklist',)])
            calls = (ws / 'state' / 'model_calls.jsonl').read_text().splitlines()
            self.assertEqual(len(calls), 3)

    def test_crash_rehearsal_exit_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = make_workspace(tmp)
            drop_fixture(ws, 'call-0412')
            cli(ws, 'accept', '--now', '1000')
            p = cli(ws, 'work', '--now', '1000', crash='after_model')
            self.assertEqual(p.returncode, 75)
            self.assertEqual(query(ws, 'SELECT COUNT(*) FROM summaries'), [(0,)])

    def test_non_transcripts_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = make_workspace(tmp)
            (ws / 'inbox' / 'notes.md').write_text('not a transcript')
            (ws / 'inbox' / '.call-0999.txt').write_text('upload in progress')
            p = cli(ws, 'accept', '--now', '1000')
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(query(ws, 'SELECT COUNT(*) FROM jobs'), [(0,)])
            self.assertEqual(sorted(x.name for x in (ws / 'inbox').iterdir()), ['.call-0999.txt', 'notes.md'])


VALID = {'title': ' Sync ', 'bullets': ['a ', ' b'], 'action_items': [{'owner': 'Lea', 'task': ' write it '}]}


class OutputContract(unittest.TestCase):
    def test_valid_summary_is_normalised(self):
        self.assertEqual(parse_summary(json.dumps(VALID)),
                         {'title': 'Sync', 'bullets': ['a', 'b'],
                          'action_items': [{'owner': 'Lea', 'task': 'write it'}]})

    def test_fenced_json_is_accepted(self):
        raw = '```json\n' + json.dumps(VALID) + '\n```'
        self.assertEqual(parse_summary(raw)['title'], 'Sync')

    def test_action_items_are_optional(self):
        self.assertEqual(parse_summary('{"title": "t", "bullets": ["x"]}')['action_items'], [])

    def test_contract_violations_are_rejected(self):
        for raw in ['Sure! Here is the summary.', '[1, 2]', '{"title": "", "bullets": ["a"]}',
                    '{"title": "t", "bullets": []}', '{"title": "t", "bullets": ["a"] , "action_items": [{"owner": "x"}]}',
                    json.dumps({'title': 'x' * 121, 'bullets': ['a']}),
                    json.dumps({'title': 't', 'bullets': ['b'] * 9})]:
            with self.subTest(raw=raw[:40]), self.assertRaises(ModelOutputError):
                parse_summary(raw)


class ConfigAndExport(unittest.TestCase):
    def test_relative_paths_resolve_against_config_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'cfg.json'
            path.write_text(json.dumps({'db_path': 'x/y.db', 'model': {'max_attempts': 5}}))
            cfg = config.load(path)
            self.assertEqual(cfg.db_path, Path(tmp).resolve() / 'x' / 'y.db')
            self.assertEqual(cfg.max_attempts, 5)
            self.assertEqual(cfg.model_name, 'stub-summarizer-2')
            self.assertEqual(cfg.backoff(1), 2)
            self.assertEqual(cfg.backoff(7), 30)

    def test_export_row_collapses_whitespace(self):
        job = {'id': 4, 'source': 'call-0004'}
        summary = {'title': 'A\ttitle', 'bullets': ['one\nline', 'two'],
                   'action_items': [{'owner': 'Lea', 'task': 'send  notes'}]}
        self.assertEqual(export.format_row(export.row(job, summary, 'm')),
                         '4\tcall-0004\tA title\tone line | two\tLea: send notes\tm\n')


def node(code, *args):
    p = subprocess.run(['node', '--experimental-strip-types', '--no-warnings', '--input-type=module',
                        '-e', code, *args], cwd=REPO, capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise AssertionError(p.stderr)
    return p.stdout


class StatusPage(unittest.TestCase):
    def test_overview_counts_pending_and_done(self):
        snap = {'generated_at': 100, 'counts': {'queued': 2, 'running': 1, 'done': 4}, 'jobs': []}
        out = node("import {overview} from './ui/status.ts'; const o = overview(%s); "
                   "console.log(JSON.stringify([o.total, o.pending, o.done]))" % json.dumps(snap))
        self.assertEqual(json.loads(out), [7, 3, 4])

    def test_job_line(self):
        job = {'id': 7, 'source': 'call-0412', 'state': 'done', 'attempts': 1, 'error': None, 'updated_at': 40}
        out = node("import {jobLine} from './ui/status.ts'; console.log(JSON.stringify(jobLine(%s, 100)))"
                   % json.dumps(job))
        self.assertEqual(json.loads(out), '    7  call-0412      done (1 attempt), 1m ago')

    def test_render_entry_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'status.json'
            path.write_text(json.dumps({'generated_at': 5, 'counts': {'done': 1},
                                        'jobs': [{'id': 1, 'source': 'call-0001', 'state': 'done',
                                                  'attempts': 1, 'error': None, 'updated_at': 5}]}))
            p = subprocess.run(['node', '--experimental-strip-types', '--no-warnings', 'ui/render.ts', str(path)],
                               cwd=REPO, capture_output=True, text=True, timeout=30)
            self.assertEqual(p.returncode, 0, p.stderr)
            lines = p.stdout.splitlines()
            self.assertTrue(lines[0].startswith('1 job: '))
            self.assertIn('call-0001', lines[1])
'''

REFERENCE1 = {
    'pipeline/export.py': r'''"""Export v1: the TSV file the downstream reporting team imports.

The format is frozen (docs/contracts.md, "Export v1"):

    header  job_id, source, title, bullets, action_items, model
    bullets joined with " | "; action items as "owner: task" joined with " | "
    UTF-8, "\\n" line endings, tabs/newlines inside values collapsed to one space

A job appears at most once (D-004): appending a row for a job that is already
exported is a no-op.
"""
from __future__ import annotations

import os
from pathlib import Path

from .textutil import one_line

HEADER = ('job_id', 'source', 'title', 'bullets', 'action_items', 'model')
JOIN = ' | '


def row(job: dict, summary: dict, model: str) -> tuple:
    actions = JOIN.join(f"{i['owner']}: {i['task']}" for i in summary['action_items'])
    return (job['id'], job['source'], summary['title'], JOIN.join(summary['bullets']),
            actions, model)


def format_row(values) -> str:
    return '\t'.join(one_line(v) for v in values) + '\n'


def exported_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lines = path.read_text(encoding='utf-8').splitlines()
    return {line.split('\t', 1)[0] for line in lines[1:] if line}


def append_row(path: Path, job: dict, summary: dict, model: str) -> bool:
    """Append the job's row unless the export already has one. Returns True if written."""
    if str(job['id']) in exported_ids(path):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    new = not path.exists() or path.stat().st_size == 0
    with path.open('a', encoding='utf-8', newline='') as fh:
        if new:
            fh.write(format_row(HEADER))
        fh.write(format_row(row(job, summary, model)))
        fh.flush()
        os.fsync(fh.fileno())
    return True


def rebuild(path: Path, store) -> int:
    """Rewrite the whole export from the summaries table (ops, after DB repairs)."""
    lines = [format_row(HEADER)]
    seen = set()
    for s in store.summaries():
        if s['job_id'] in seen:
            continue
        seen.add(s['job_id'])
        job = {'id': s['job_id'], 'source': s['source']}
        lines.append(format_row(row(job, s['body'], s['model'])))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(''.join(lines), encoding='utf-8', newline='')
    tmp.replace(path)
    return len(lines) - 1


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    lines = path.read_text(encoding='utf-8').splitlines()
    header = lines[0].split('\t')
    return [dict(zip(header, line.split('\t'))) for line in lines[1:] if line]
''',
    'pipeline/ingest.py': r'''"""Accept transcripts dropped into the inbox by the recorder's uploader.

The uploader writes `<inbox>/call-<n>.txt` and considers the upload delivered
once the file disappears from the inbox. Order of steps (D-003): archive copy,
commit the job, only then remove the inbox file. A known source is not
accepted twice (D-002).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import faults

SUFFIX = '.txt'


def pending(cfg) -> list[Path]:
    """Inbox files ready for acceptance, oldest name first."""
    if not cfg.inbox_dir.is_dir():
        return []
    return sorted(p for p in cfg.inbox_dir.iterdir()
                  if p.is_file() and p.suffix == SUFFIX and not p.name.startswith('.'))


def _archive(path: Path, target: Path) -> None:
    tmp = target.with_name(f'.{target.name}.tmp')
    shutil.copyfile(path, tmp)
    os.replace(tmp, target)


def accept_file(cfg, store, path: Path, now: int) -> int:
    source = path.stem
    existing = store.find_by_source(source)
    if existing is not None:
        # Redelivery of an upload we already hold (D-002).
        path.unlink(missing_ok=True)
        return existing['id']
    cfg.archive_dir.mkdir(parents=True, exist_ok=True)
    target = cfg.archive_dir / path.name
    _archive(path, target)
    faults.checkpoint('after_archive')
    job_id = store.add_job(source, target, now)
    path.unlink(missing_ok=True)
    return job_id


def accept_all(cfg, store, now: int, log=print) -> list[int]:
    accepted = []
    for path in pending(cfg):
        job_id = accept_file(cfg, store, path, now)
        log(f'accepted {path.name} as job {job_id}')
        accepted.append(job_id)
    return accepted
''',
    'pipeline/output.py': r'''"""Prompt and structured-output contract (docs/contracts.md)."""
from __future__ import annotations

import json
import re

from .errors import ModelOutputError, TranscriptError

MAX_TITLE = 120
MAX_BULLETS = 8
_FENCE = re.compile(r'^```(?:json)?\s*(.*?)\s*```$', re.S)

INSTRUCTIONS = """You summarise recorded business calls.
Return ONLY a JSON object with these keys:
  "title": string, at most 120 characters
  "bullets": list of 1 to 8 short strings
  "action_items": list of {"owner": string, "task": string} (may be empty)
Do not add commentary before or after the JSON.
"""

SEPARATOR = '---'


def build_prompt(transcript: str, max_chars: int) -> str:
    """Build the prompt. Never truncates (D-007): unusable input raises TranscriptError."""
    body = transcript.strip('﻿')
    if not body.strip():
        raise TranscriptError('empty transcript')
    if len(body) > max_chars:
        raise TranscriptError(f'transcript has {len(body)} characters, limit is {max_chars}')
    return f'{INSTRUCTIONS}\n{SEPARATOR}\n{body}\n{SEPARATOR}\n'


def _strip_fence(raw: str) -> str:
    text = str(raw).strip()
    match = _FENCE.match(text)
    return match.group(1) if match else text


def validate(data) -> list[str]:
    """Return a list of contract violations (empty when the summary is valid)."""
    if not isinstance(data, dict):
        return ['top level must be a JSON object']
    problems = []
    title = data.get('title')
    if not isinstance(title, str) or not title.strip():
        problems.append('title must be a non-empty string')
    elif len(title.strip()) > MAX_TITLE:
        problems.append(f'title longer than {MAX_TITLE} characters')
    bullets = data.get('bullets')
    if (not isinstance(bullets, list) or not 1 <= len(bullets) <= MAX_BULLETS
            or not all(isinstance(b, str) and b.strip() for b in bullets)):
        problems.append(f'bullets must be 1-{MAX_BULLETS} non-empty strings')
    items = data.get('action_items', [])
    if not isinstance(items, list) or not all(
            isinstance(i, dict) and isinstance(i.get('owner'), str)
            and isinstance(i.get('task'), str) and i['task'].strip() for i in items):
        problems.append('action_items must be a list of {owner, task} strings')
    return problems


def normalize(data: dict) -> dict:
    return {
        'title': data['title'].strip(),
        'bullets': [b.strip() for b in data['bullets']],
        'action_items': [{'owner': i['owner'].strip(), 'task': i['task'].strip()}
                         for i in data.get('action_items', [])],
    }


def parse_summary(raw: str) -> dict:
    """Strict parser: returns a normalised summary or raises ModelOutputError."""
    try:
        data = json.loads(_strip_fence(raw))
    except (json.JSONDecodeError, TypeError) as exc:
        raise ModelOutputError(f'output is not JSON ({exc.__class__.__name__})') from None
    problems = validate(data)
    if problems:
        raise ModelOutputError('; '.join(problems))
    return normalize(data)


def salvage_summary(raw: str) -> dict:
    """Best-effort summary from whatever the model said (ops request, 2025-06).

    Never raises: unusable output becomes a one-bullet summary carrying the raw
    text, so the export row is never empty during an incident.
    """
    try:
        return parse_summary(raw)
    except ModelOutputError:
        text = ' '.join(str(raw).split())
        return {'title': 'Summary', 'bullets': [text[:500] or '(empty)'], 'action_items': []}
''',
    'pipeline/requeue.py': r'''"""Put failed jobs back into the queue (ops runbook, "Requeue"; D-008).

requeue() moves failed_model jobs back to `queued` and resets their attempts.
failed_app jobs stay: retrying cannot help until the input is fixed.
With inline=True the queue is processed right away in this process by the
regular worker (same validation, retries, failure states and D-004 writes);
ops use that during incidents while the worker service is stopped.
"""
from __future__ import annotations

from .worker import Worker

REQUEUEABLE = ('failed_model', 'failed')   # 'failed' predates D-006


def requeue(cfg, store, now: int, inline: bool = False, client=None, log=print) -> list[int]:
    ids = [job['id'] for job in store.jobs() if job['state'] in REQUEUEABLE]
    for job_id in ids:
        store.requeue(job_id, now)
        log(f'requeued job {job_id}')
    if inline and ids:
        Worker(cfg, store, client=client, log=log).run(now)
    return ids
''',
    'pipeline/status.py': r'''"""Status snapshot for the ops UI (docs/contracts.md).

The worker rewrites out/status.json after every run; `cli status` writes and
prints it on demand. ui/status.ts renders it.
"""
from __future__ import annotations

import json
from pathlib import Path

from .store import STATES


def _state(state: str) -> str:
    return 'failed_model' if state == 'failed' else state   # D-006 legacy rows


def snapshot(store, now: int) -> dict:
    counts = {state: 0 for state in STATES}
    for state, n in store.count_by_state().items():
        counts[_state(state)] = counts.get(_state(state), 0) + n
    jobs = [{
        'id': j['id'],
        'source': j['source'],
        'state': _state(j['state']),
        'attempts': j['attempts'],
        'error': j['error'],
        'updated_at': j['updated_at'],
    } for j in store.jobs()]
    return {'generated_at': now, 'counts': counts, 'jobs': jobs}


def write(path: Path, snap: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(snap, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)
''',
    'pipeline/store.py': r'''"""SQLite persistence for jobs and summaries.

Job lifecycle (docs/decisions.md D-003, D-006):

    queued -> running -> done | failed_model | failed_app
    running (lease expired) -> running (claimed again)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

STATES = ('queued', 'running', 'done', 'failed_model', 'failed_app')
SCHEMA = """
-- Pipeline schema. Changes must be additive (docs/operations.md, "Schema changes").
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,             -- inbox file stem, e.g. call-0412
  transcript_path TEXT NOT NULL,    -- archive copy the worker reads
  state TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  lease_until INTEGER,              -- epoch seconds, only meaningful while running
  error TEXT,
  accepted_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS jobs_source ON jobs(source);

CREATE TABLE IF NOT EXISTS summaries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id),
  title TEXT NOT NULL,
  body TEXT NOT NULL,               -- normalised summary JSON (docs/contracts.md)
  model TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS summaries_job ON summaries(job_id);

CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT
);
"""
SCHEMA_VERSION = '3'


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.migrate()

    @contextmanager
    def tx(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        else:
            self.db.execute('COMMIT')

    def migrate(self) -> None:
        """Bring any older database up to date. Additive changes only."""
        self.db.executescript(SCHEMA)
        with self.tx():
            self.db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                            (SCHEMA_VERSION,))
            # D-006: rows from before the split count as model failures.
            self.db.execute("UPDATE jobs SET state = 'failed_model' WHERE state = 'failed'")

    def close(self) -> None:
        self.db.close()

    # -- jobs -------------------------------------------------------------
    def add_job(self, source: str, transcript_path, now: int) -> int:
        """Create the job for `source`, or return the existing one (D-002)."""
        with self.tx():
            row = self.db.execute('SELECT id FROM jobs WHERE source = ? ORDER BY id LIMIT 1',
                                  (source,)).fetchone()
            if row is not None:
                return row['id']
            cur = self.db.execute(
                'INSERT INTO jobs(source, transcript_path, state, accepted_at, updated_at) '
                "VALUES(?, ?, 'queued', ?, ?)", (source, str(transcript_path), now, now))
            return cur.lastrowid

    def job(self, job_id: int):
        row = self.db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
        return dict(row) if row else None

    def find_by_source(self, source: str):
        row = self.db.execute('SELECT * FROM jobs WHERE source = ? ORDER BY id LIMIT 1',
                              (source,)).fetchone()
        return dict(row) if row else None

    def jobs(self, state: str | None = None) -> list[dict]:
        if state is None:
            rows = self.db.execute('SELECT * FROM jobs ORDER BY id')
        else:
            rows = self.db.execute('SELECT * FROM jobs WHERE state = ? ORDER BY id', (state,))
        return [dict(r) for r in rows]

    def claim(self, now: int, lease_seconds: int):
        """Lease the oldest queued job or expired lease to the caller (D-003)."""
        with self.tx():
            row = self.db.execute(
                "SELECT id FROM jobs WHERE state = 'queued' "
                "OR (state = 'running' AND (lease_until IS NULL OR lease_until <= ?)) "
                'ORDER BY id LIMIT 1', (now,)).fetchone()
            if row is None:
                return None
            self.db.execute(
                "UPDATE jobs SET state = 'running', lease_until = ?, updated_at = ? WHERE id = ?",
                (now + lease_seconds, now, row['id']))
        return self.job(row['id'])

    def bump_attempt(self, job_id: int) -> int:
        with self.tx():
            self.db.execute('UPDATE jobs SET attempts = attempts + 1 WHERE id = ?', (job_id,))
        return self.job(job_id)['attempts']

    def finish(self, job_id: int, now: int) -> None:
        with self.tx():
            self.db.execute(
                "UPDATE jobs SET state = 'done', lease_until = NULL, error = NULL, updated_at = ? "
                'WHERE id = ?', (now, job_id))

    def fail(self, job_id: int, state: str, error: str, now: int) -> None:
        if state not in ('failed_model', 'failed_app'):
            raise ValueError(f'not a failure state: {state!r}')
        with self.tx():
            self.db.execute(
                'UPDATE jobs SET state = ?, lease_until = NULL, error = ?, updated_at = ? '
                'WHERE id = ?', (state, error, now, job_id))

    def requeue(self, job_id: int, now: int) -> None:
        with self.tx():
            self.db.execute(
                "UPDATE jobs SET state = 'queued', attempts = 0, error = NULL, lease_until = NULL, "
                'updated_at = ? WHERE id = ?', (now, job_id))

    def count_by_state(self) -> dict:
        return {r['state']: r['n'] for r in
                self.db.execute('SELECT state, COUNT(*) AS n FROM jobs GROUP BY state')}

    # -- summaries ----------------------------------------------------------
    def save_summary(self, job_id: int, summary: dict, model: str, now: int) -> None:
        """Store the job's summary; a rerun replaces it instead of adding one (D-004)."""
        body = json.dumps(summary, sort_keys=True)
        with self.tx():
            row = self.db.execute('SELECT id FROM summaries WHERE job_id = ? ORDER BY id LIMIT 1',
                                  (job_id,)).fetchone()
            if row is None:
                self.db.execute(
                    'INSERT INTO summaries(job_id, title, body, model, created_at) '
                    'VALUES(?, ?, ?, ?, ?)', (job_id, summary['title'], body, model, now))
            else:
                self.db.execute(
                    'UPDATE summaries SET title = ?, body = ?, model = ?, created_at = ? WHERE id = ?',
                    (summary['title'], body, model, now, row['id']))

    def summaries(self, job_id: int | None = None) -> list[dict]:
        sql = ('SELECT s.*, j.source FROM summaries s JOIN jobs j ON j.id = s.job_id')
        if job_id is None:
            rows = self.db.execute(sql + ' ORDER BY s.job_id, s.id')
        else:
            rows = self.db.execute(sql + ' WHERE s.job_id = ? ORDER BY s.id', (job_id,))
        out = []
        for r in rows:
            d = dict(r)
            d['body'] = json.loads(d['body'])
            out.append(d)
        return out
''',
    'pipeline/worker.py': r'''"""The worker: claims jobs and turns transcripts into validated summaries.

One job, step by step:

    claim -> read archived transcript -> model call (with retries)
          -> parse/validate -> summary row -> export row -> done

Every step after the claim may run again after a crash (D-003), so the writes
are idempotent (D-004). Model failures are retried and end in failed_model;
input problems end in failed_app without a model call (D-006, D-007).
"""
from __future__ import annotations

import time
from pathlib import Path

from . import export, faults, output, status
from .errors import ModelError, TranscriptError
from .model_client import make_client
from .textutil import mask_email, preview, read_text


class Worker:
    def __init__(self, cfg, store, client=None, sleep=time.sleep, log=print):
        self.cfg = cfg
        self.store = store
        self.client = client or make_client(cfg)
        self.sleep = sleep
        self.log = log

    def run(self, now: int, max_jobs: int | None = None) -> list[tuple[int, str]]:
        """Process claimable jobs until none is left (or max_jobs is reached)."""
        results = []
        while max_jobs is None or len(results) < max_jobs:
            job = self.store.claim(now, self.cfg.lease_seconds)
            if job is None:
                break
            faults.checkpoint('after_claim')
            results.append((job['id'], self.process(job, now)))
        status.write(self.cfg.status_path, status.snapshot(self.store, now))
        return results

    def _prompt(self, job: dict) -> str:
        path = Path(job['transcript_path'])
        try:
            text = read_text(path)
        except OSError as exc:
            raise TranscriptError(f'archive copy unreadable: {exc.__class__.__name__}') from None
        return output.build_prompt(text, self.cfg.max_transcript_chars)

    def process(self, job: dict, now: int) -> str:
        try:
            prompt = self._prompt(job)
        except TranscriptError as exc:
            self.store.fail(job['id'], 'failed_app', f'TranscriptError: {exc}', now)
            self.log(f"job {job['id']} ({job['source']}) needs attention: {exc}")
            return 'failed_app'
        while True:
            attempt = self.store.bump_attempt(job['id'])
            try:
                raw = self.client.complete(prompt, key=job['source'], attempt=attempt)
                faults.checkpoint('after_model')
                summary = output.parse_summary(raw)
            except ModelError as exc:
                message = f'{type(exc).__name__}: {exc}'
                self.log(f"job {job['id']} attempt {attempt} failed: {mask_email(message)}")
                if attempt >= self.cfg.max_attempts:
                    self.store.fail(job['id'], 'failed_model', message, now)
                    return 'failed_model'
                self.sleep(self.cfg.backoff(attempt))
                continue
            self.store.save_summary(job['id'], summary, self.client.name, now)
            faults.checkpoint('after_summary')
            export.append_row(self.cfg.export_path, job, summary, self.client.name)
            faults.checkpoint('after_export')
            self.store.finish(job['id'], now)
            self.log(f"job {job['id']} ({job['source']}) done: {preview(summary['title'])}")
            return 'done'
''',
    'ui/status.ts': r'''// Ops status page model: reads out/status.json (docs/contracts.md).
// Runtime: node with type stripping (no tsc build step; erasable TypeScript only).

export function padLeft(value: string | number, width: number): string {
  const s = String(value);
  return s.length >= width ? s : ' '.repeat(width - s.length) + s;
}

export function padRight(value: string, width: number): string {
  return value.length >= width ? value : value + ' '.repeat(width - value.length);
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

export function age(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '?';
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

export interface JobRow {
  id: number;
  source: string;
  state: string;
  attempts: number;
  error: string | null;
  updated_at: number;
}

export interface Snapshot {
  generated_at: number;
  counts: Record<string, number>;
  jobs: JobRow[];
}

export interface Overview {
  total: number;
  pending: number;
  done: number;
  retryable: number;
  attention: number;
}

const LABELS: Record<string, string> = {
  queued: 'waiting',
  running: 'in progress',
  done: 'done',
  failed_model: 'retryable',
  failed_app: 'needs attention',
  failed: 'retryable', // rows from before D-006
};

export function label(state: string): string {
  return LABELS[state] ?? state;
}

export function parseSnapshot(text: string): Snapshot {
  const s = JSON.parse(text);
  if (!s || typeof s !== 'object' || typeof s.counts !== 'object' || s.counts === null) {
    throw new Error('not a status snapshot');
  }
  s.jobs ??= [];
  return s as Snapshot;
}

export function overview(s: Snapshot): Overview {
  const c = s.counts ?? {};
  const n = (k: string): number => c[k] ?? 0;
  const total = Object.values(c).reduce((a, b) => a + b, 0);
  return {
    total,
    pending: n('queued') + n('running'),
    done: n('done'),
    retryable: n('failed_model') + n('failed'),
    attention: n('failed_app'),
  };
}

export function headline(s: Snapshot): string {
  const o = overview(s);
  return `${plural(o.total, 'job')}: ${o.pending} pending, ${o.done} done, ` +
    `${o.retryable} retryable, ${o.attention} need attention`;
}

export function jobLine(j: JobRow, now?: number): string {
  let line = `${padLeft(j.id, 5)}  ${padRight(j.source, 14)} ${label(j.state)}`;
  if (j.attempts > 0) line += ` (${plural(j.attempts, 'attempt')})`;
  if (now !== undefined) line += `, ${age(now - j.updated_at)} ago`;
  return line;
}

export function render(s: Snapshot): string {
  const lines = [headline(s)];
  for (const j of s.jobs) lines.push(jobLine(j, s.generated_at));
  return lines.join('\n');
}
''',
}

REFERENCE2 = {
    'README.md': r'''# Transcript pipeline

Offline transcript-to-summary pipeline. Call recordings are transcribed
elsewhere; the uploader drops `call-<n>.txt` files into the inbox, this
pipeline turns them into validated summaries for the reporting team and keeps
an ops status page current. No network access, no real model: the model client
replays canned responses (docs/decisions.md D-001).

## Layout

| Path                    | What                                                   |
| ----------------------- | ------------------------------------------------------ |
| `pipeline/ingest.py`    | accepts inbox files as jobs, archive copy              |
| `pipeline/store.py`     | SQLite jobs + summaries, schema and migrations         |
| `pipeline/worker.py`    | claim, model call with retries, validation, writes     |
| `pipeline/requeue.py`   | puts failed jobs back, optional inline processing      |
| `pipeline/model_client.py` | stub model client and model audit log               |
| `pipeline/redact.py`    | personal-data redaction (D-009)                        |
| `pipeline/output.py`    | prompt contract, structured-output validation          |
| `pipeline/export.py`    | Export v1 (TSV for the reporting team, frozen format)  |
| `pipeline/status.py`    | status snapshot for the UI                             |
| `pipeline/faults.py`    | crash rehearsal checkpoints                            |
| `pipeline/legacy_batch.py` | deprecated pre-queue batch summariser (not wired)   |
| `ui/`                   | TypeScript status page model, run with node            |
| `scripts/`              | crash rehearsal                                        |
| `docs/`                 | decisions (authoritative), contracts, operations and incident notes |

## Checks

    python3 -m unittest discover -s tests -t .

The UI tests need node 22+ (type stripping). Keep public interfaces, the
Export v1 format and legacy behaviour unless a decision says otherwise, and
record what changed and what was actually verified in docs/handoff.md.
''',
    'docs/contracts.md': r'''# Contracts

Interfaces between the pipeline, the model and its consumers.

# Part 1: model output and Export v1

## Model output (summary JSON)

The model must return one JSON object, optionally wrapped in a ```json fence:

| key            | type                              | rule                          |
| -------------- | --------------------------------- | ----------------------------- |
| `title`        | string                            | non-empty, at most 120 chars  |
| `bullets`      | list of strings                   | 1 to 8 non-empty strings      |
| `action_items` | list of `{"owner", "task"}`       | optional, strings, task non-empty |

`pipeline/output.py` validates and normalises (strips whitespace). The stored
summary (`summaries.body`) is the normalised object with exactly these keys.

## Export v1 (frozen)

`out/summaries_v1.tsv`, UTF-8, `\n` line endings, tab separated, one header
line followed by one line per summarised job:

    job_id  source  title  bullets  action_items  model

- `bullets`: joined with ` | `
- `action_items`: each item as `owner: task`, joined with ` | `; empty if none
- tabs, newlines and repeated blanks inside a value collapse to a single space

The reporting team's importer rejects files with a different header or column
count. Do not add, remove, rename or reorder columns.

# Part 2: status (pipeline -> ops UI)

Written by `pipeline/status.py` to `out/status.json`, read by `ui/status.ts`.
Revised 2026-02-02 for D-006.

## status.json

    {
      "generated_at": <epoch seconds>,
      "counts": {<state>: <number of jobs>, ...},
      "jobs": [{"id", "source", "state", "attempts", "error", "updated_at", "redacted"}, ...]
    }

- `counts` has exactly one key per job state: `queued`, `running`, `done`,
  `failed_model`, `failed_app`, each present even when zero.
- `jobs[].state` is the job's real state as stored in the database.
- `jobs[].redacted` is true when personal data was replaced in the job's
  transcript (D-009); false for jobs accepted before redaction existed.

## UI (ui/status.ts)

| state          | `label()`         | `overview()` field |
| -------------- | ----------------- | ------------------ |
| `queued`       | `waiting`         | `pending`          |
| `running`      | `in progress`     | `pending`          |
| `done`         | `done`            | `done`             |
| `failed_model` | `retryable`       | `retryable`        |
| `failed_app`   | `needs attention` | `attention`        |

`jobLine()` appends ` [redacted]` for jobs with `redacted: true`; rows without
the field (older snapshots) render as before.

`overview()` also returns `total`, the sum of all counts.
`headline()` reads, for example:

    11 jobs: 3 pending, 4 done, 3 retryable, 1 need attention

Operators run `requeue` for retryable jobs; jobs that need attention need a
human to fix the input first.
''',
    'docs/decisions.md': r'''# Decision log

Newest last. A later decision supersedes an earlier one where they conflict, and
code comments older than a decision do not override it. Proposed entries are
not in force until they are marked approved.

## D-001 (2025-03-04) Offline stub model with canned responses

The pipeline talks to the summarizer only through a client with
`complete(prompt, *, key, attempt) -> str`. In this repository the client is
`StubModelClient`, which replays `<responses_dir>/<source>.json`; it never
touches the network. The model audit log (`AuditedClient`) records every call.

## D-002 (2025-04-11) One job per upload

The recorder names every upload `call-<n>.txt` and its uploader re-sends a file
when it does not see it leave the inbox in time, so the same file can arrive
more than once, also after it was processed. A source name (the file stem) is
accepted at most once: accepting a known source again returns the existing job
and removes the redelivered inbox file. It never creates a second job.

## D-003 (2025-05-20) Accepted means durable

"Accepted" means the job row is committed. Guarantees:

1. An inbox file is removed only after its job is committed. The archive copy
   the worker reads is written before the job is committed. A crash at any
   point of `accept` therefore leaves either the file in the inbox or a
   committed job, and the next `accept` run completes the hand-over.
2. `running` is a lease, not a promise. `claim` sets
   `lease_until = now + lease_seconds`. A `running` job whose lease has expired
   (`lease_until <= now`) is claimable again, exactly like a queued job (oldest
   job id first). A live lease is never taken over: its worker may still be busy.
3. Consequently the worker steps after the claim (model call, summary row,
   export row, finish) can run more than once for the same job. See D-004.

## D-004 (2025-05-20) Exactly one summary per job

Retries, re-claims and requeues must not create duplicates. A job has at most
one row in `summaries`, and Export v1 contains at most one row per job. This
applies to every code path that writes summaries or export rows.

## D-005 (2025-11-18) No salvage of malformed model output

Supersedes the 2025-06 ops request to salvage partial output. Model output that
is not valid JSON or violates docs/contracts.md is a model failure: it is
retried like a timeout and is never stored or exported. Incident 2025-11-12:
salvaged "Sure! Here is ..." text reached a customer report.

## D-006 (2026-02-02) Model failures and application failures are different

The single `failed` state is replaced by two terminal failure states:

- `failed_model`: every one of `model.max_attempts` model attempts failed
  (timeout, rate limit, outage, or output rejected under D-005). Trying again
  later can succeed.
- `failed_app`: the problem is on our side or in the input: empty transcript,
  transcript longer than `max_transcript_chars` (D-007), archive copy missing
  or unreadable. The model is not called for these jobs, and they are not
  retried; retrying cannot help until someone fixes the input.

Only model failures are retried within a run, with the configured backoff.
`jobs.attempts` counts model calls. The `error` column keeps the last error
message. Status and UI report both states separately (docs/contracts.md).
Rows still carrying the old `failed` state count as `failed_model`.

## D-007 (2026-03-09) Never truncate transcripts

The prompt builder used to cut transcripts at `max_transcript_chars`.
Incident 2026-03-02: action items at the end of long calls silently vanished.
A transcript longer than `max_transcript_chars` characters is an application
failure (`failed_app`); ops split such recordings by hand.

## D-008 (2026-03-09) Requeue only what can succeed

`requeue` moves `failed_model` jobs back to `queued` with `attempts` reset to 0.
`failed_app` jobs stay where they are. `requeue --inline` processes the requeued
jobs immediately and follows exactly the same rules as the worker (validation,
retries, failure states, D-004).

## D-009 (2026-08-21) Redaction of personal data

Status: approved 2026-09-27 by legal, with phone numbers in scope (see the
last section of this entry). Implemented in `pipeline/redact.py`.

Context: transcripts contain e-mail addresses and phone numbers of call
participants, and models echo them into action items.

Proposal:

- Redact before anything is persisted by the pipeline: archive copy, database
  rows (jobs, summaries, error texts), Export v1, status snapshot and model audit
  log. The model therefore only ever sees redacted text, and model output is
  redacted before it is stored or logged.
- E-mail addresses become `[EMAIL]`. Shape: a local part of letters, digits and
  `._%+-`, then `@`, then dot-separated labels of letters, digits and hyphens,
  ending in a top-level label of at least two letters.
- Phone numbers (added on approval; originally left out for fear of false
  positives). The agreed shape is `+` followed by 8-15 digits, or a national number
  `0` followed by 9-10 further digits; digits may be grouped with single spaces,
  hyphens or slashes, and the number must not touch other letters or digits.
  They become `[PHONE]`. Timestamps (`00:12:05`), dates (`2026-09-14`), ticket
  IDs (`TCK-2024-00017`) and amounts must never match.
- Status: every job in status.json gets a boolean `redacted`, true when at
  least one replacement was made in its transcript. The UI job line appends
  ` [redacted]` for such jobs. Jobs accepted before the change are `false`.
- Export v1 keeps its exact format; redacted values simply contain the tokens.
- `textutil.mask_email` is for console log lines only and is not a redaction.

Approval note (2026-09-27): phone numbers are redacted as well; everything else
as proposed. Export v1 is unchanged.
''',
    'pipeline/ingest.py': r'''"""Accept transcripts dropped into the inbox by the recorder's uploader.

The uploader writes `<inbox>/call-<n>.txt` and considers the upload delivered
once the file disappears from the inbox. Order of steps (D-003): archive copy,
commit the job, only then remove the inbox file. A known source is not
accepted twice (D-002). The archive copy is redacted (D-009): the raw upload
is never written anywhere by the pipeline.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import faults
from .redact import redact
from .textutil import read_text

SUFFIX = '.txt'


def pending(cfg) -> list[Path]:
    """Inbox files ready for acceptance, oldest name first."""
    if not cfg.inbox_dir.is_dir():
        return []
    return sorted(p for p in cfg.inbox_dir.iterdir()
                  if p.is_file() and p.suffix == SUFFIX and not p.name.startswith('.'))


def _archive(text: str, target: Path) -> None:
    tmp = target.with_name(f'.{target.name}.tmp')
    with tmp.open('w', encoding='utf-8', newline='') as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, target)


def accept_file(cfg, store, path: Path, now: int) -> int:
    source = path.stem
    existing = store.find_by_source(source)
    if existing is not None:
        # Redelivery of an upload we already hold (D-002).
        path.unlink(missing_ok=True)
        return existing['id']
    text, replacements = redact(read_text(path))
    cfg.archive_dir.mkdir(parents=True, exist_ok=True)
    target = cfg.archive_dir / path.name
    _archive(text, target)
    faults.checkpoint('after_archive')
    job_id = store.add_job(source, target, now, redacted=replacements > 0)
    path.unlink(missing_ok=True)
    return job_id


def accept_all(cfg, store, now: int, log=print) -> list[int]:
    accepted = []
    for path in pending(cfg):
        job_id = accept_file(cfg, store, path, now)
        log(f'accepted {path.name} as job {job_id}')
        accepted.append(job_id)
    return accepted
''',
    'pipeline/model_client.py': r'''"""Model clients.

StubModelClient is the only model client in this repository. It replays canned
responses from <responses_dir>/<source>.json so every run is deterministic and
offline. Response file format:

    {"attempts": [<response>, ...], "default": <response>}

Model attempt N (1-based) uses attempts[N-1] when present, otherwise "default".
A <response> is one of

    {"kind": "ok", "text": "..."}     the model answered (the text may be garbage)
    {"kind": "timeout"}                the provider timed out
    {"kind": "rate_limited"}           the provider answered 429

A missing file or entry behaves like a provider outage (ModelUnavailable).

AuditedClient wraps a client and appends one JSON line per call to the model
audit log (docs/operations.md, "Model audit log"). Prompt and response are
redacted before they are logged (D-009).
"""
from __future__ import annotations

import json
from pathlib import Path

from .errors import ModelRateLimited, ModelTimeout, ModelUnavailable
from .redact import redact_text


class StubModelClient:
    def __init__(self, responses_dir, name: str = 'stub-summarizer-2'):
        self.responses_dir = Path(responses_dir)
        self.name = name

    def _response(self, key: str, attempt: int):
        path = self.responses_dir / f'{key}.json'
        if not path.is_file():
            return None
        spec = json.loads(path.read_text(encoding='utf-8'))
        sequence = spec.get('attempts') or []
        if 1 <= attempt <= len(sequence):
            return sequence[attempt - 1]
        return spec.get('default')

    def complete(self, prompt: str, *, key: str, attempt: int) -> str:
        response = self._response(key, attempt)
        if response is None:
            raise ModelUnavailable(f'no canned response for {key}')
        kind = response.get('kind')
        if kind == 'timeout':
            raise ModelTimeout(f'{self.name} did not answer in time')
        if kind == 'rate_limited':
            raise ModelRateLimited(f'{self.name} answered 429')
        if kind == 'ok':
            return str(response.get('text', ''))
        raise ModelUnavailable(f'unknown canned response kind {kind!r}')


class AuditedClient:
    """Records every call: key, attempt, model, prompt, outcome and response."""

    def __init__(self, inner, log_path):
        self.inner = inner
        self.log_path = Path(log_path)

    @property
    def name(self) -> str:
        return self.inner.name

    def complete(self, prompt: str, *, key: str, attempt: int) -> str:
        entry = {'key': key, 'attempt': attempt, 'model': self.name, 'prompt': redact_text(prompt)}
        try:
            text = self.inner.complete(prompt, key=key, attempt=attempt)
        except Exception as exc:
            entry['outcome'] = type(exc).__name__
            self._write(entry)
            raise
        entry['outcome'] = 'ok'
        entry['response'] = redact_text(text)
        self._write(entry)
        return text

    def _write(self, entry: dict) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(entry, sort_keys=True) + '\n')


def make_client(cfg):
    return AuditedClient(StubModelClient(cfg.responses_dir, cfg.model_name), cfg.calls_log)
''',
    'pipeline/redact.py': r'''"""Redaction of personal data (docs/decisions.md D-009, approved with phones).

Everything the pipeline persists passes through here first: archive copy,
database rows, Export v1, status snapshot and the model audit log.
"""
from __future__ import annotations

import re

EMAIL_TOKEN = '[EMAIL]'
PHONE_TOKEN = '[PHONE]'

EMAIL = re.compile(r'[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}(?![A-Za-z0-9-])')
# "+" and 8-15 digits, or "0" and 9-10 further digits; single space, hyphen or
# slash between digit groups; must not touch other letters or digits.
PHONE = re.compile(r'(?<![A-Za-z0-9+])(?:\+\d(?:[ /-]?\d){7,14}|0\d(?:[ /-]?\d){8,9})(?![A-Za-z0-9])')


def redact(text: str) -> tuple[str, int]:
    """Return (redacted text, number of replacements)."""
    text, emails = EMAIL.subn(EMAIL_TOKEN, text)
    text, phones = PHONE.subn(PHONE_TOKEN, text)
    return text, emails + phones


def redact_text(text: str) -> str:
    return redact(text)[0]


def redact_value(value):
    """Redact every string inside a JSON-like value (dicts, lists, strings)."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, dict):
        return {k: redact_value(v) for k, v in value.items()}
    return value
''',
    'pipeline/status.py': r'''"""Status snapshot for the ops UI (docs/contracts.md).

The worker rewrites out/status.json after every run; `cli status` writes and
prints it on demand. ui/status.ts renders it.
"""
from __future__ import annotations

import json
from pathlib import Path

from .redact import redact_text
from .store import STATES


def _state(state: str) -> str:
    return 'failed_model' if state == 'failed' else state   # D-006 legacy rows


def snapshot(store, now: int) -> dict:
    counts = {state: 0 for state in STATES}
    for state, n in store.count_by_state().items():
        counts[_state(state)] = counts.get(_state(state), 0) + n
    jobs = [{
        'id': j['id'],
        'source': j['source'],
        'state': _state(j['state']),
        'attempts': j['attempts'],
        'error': redact_text(j['error']) if j['error'] else j['error'],
        'updated_at': j['updated_at'],
        'redacted': bool(j.get('redacted')),
    } for j in store.jobs()]
    return {'generated_at': now, 'counts': counts, 'jobs': jobs}


def write(path: Path, snap: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(snap, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    tmp.replace(path)
''',
    'pipeline/store.py': r'''"""SQLite persistence for jobs and summaries.

Job lifecycle (docs/decisions.md D-003, D-006):

    queued -> running -> done | failed_model | failed_app
    running (lease expired) -> running (claimed again)
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

STATES = ('queued', 'running', 'done', 'failed_model', 'failed_app')
SCHEMA = """
-- Pipeline schema. Changes must be additive (docs/operations.md, "Schema changes").
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source TEXT NOT NULL,             -- inbox file stem, e.g. call-0412
  transcript_path TEXT NOT NULL,    -- archive copy the worker reads
  state TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  lease_until INTEGER,              -- epoch seconds, only meaningful while running
  error TEXT,
  accepted_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS jobs_source ON jobs(source);

CREATE TABLE IF NOT EXISTS summaries(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id),
  title TEXT NOT NULL,
  body TEXT NOT NULL,               -- normalised summary JSON (docs/contracts.md)
  model TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS summaries_job ON summaries(job_id);

CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT
);
"""
SCHEMA_VERSION = '3'


class Store:
    def __init__(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.db = sqlite3.connect(path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.migrate()

    @contextmanager
    def tx(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
        except BaseException:
            self.db.execute('ROLLBACK')
            raise
        else:
            self.db.execute('COMMIT')

    def migrate(self) -> None:
        """Bring any older database up to date. Additive changes only."""
        self.db.executescript(SCHEMA)
        with self.tx():
            self.db.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('schema_version', ?)",
                            (SCHEMA_VERSION,))
            # D-006: rows from before the split count as model failures.
            self.db.execute("UPDATE jobs SET state = 'failed_model' WHERE state = 'failed'")
            columns = {r['name'] for r in self.db.execute('PRAGMA table_info(jobs)')}
            if 'redacted' not in columns:
                # D-009: jobs accepted before redaction existed report false.
                self.db.execute('ALTER TABLE jobs ADD COLUMN redacted INTEGER NOT NULL DEFAULT 0')

    def close(self) -> None:
        self.db.close()

    # -- jobs -------------------------------------------------------------
    def add_job(self, source: str, transcript_path, now: int, redacted: bool = False) -> int:
        """Create the job for `source`, or return the existing one (D-002)."""
        with self.tx():
            row = self.db.execute('SELECT id FROM jobs WHERE source = ? ORDER BY id LIMIT 1',
                                  (source,)).fetchone()
            if row is not None:
                return row['id']
            cur = self.db.execute(
                'INSERT INTO jobs(source, transcript_path, state, accepted_at, updated_at, redacted) '
                "VALUES(?, ?, 'queued', ?, ?, ?)", (source, str(transcript_path), now, now, int(redacted)))
            return cur.lastrowid

    def job(self, job_id: int):
        row = self.db.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
        return dict(row) if row else None

    def find_by_source(self, source: str):
        row = self.db.execute('SELECT * FROM jobs WHERE source = ? ORDER BY id LIMIT 1',
                              (source,)).fetchone()
        return dict(row) if row else None

    def jobs(self, state: str | None = None) -> list[dict]:
        if state is None:
            rows = self.db.execute('SELECT * FROM jobs ORDER BY id')
        else:
            rows = self.db.execute('SELECT * FROM jobs WHERE state = ? ORDER BY id', (state,))
        return [dict(r) for r in rows]

    def claim(self, now: int, lease_seconds: int):
        """Lease the oldest queued job or expired lease to the caller (D-003)."""
        with self.tx():
            row = self.db.execute(
                "SELECT id FROM jobs WHERE state = 'queued' "
                "OR (state = 'running' AND (lease_until IS NULL OR lease_until <= ?)) "
                'ORDER BY id LIMIT 1', (now,)).fetchone()
            if row is None:
                return None
            self.db.execute(
                "UPDATE jobs SET state = 'running', lease_until = ?, updated_at = ? WHERE id = ?",
                (now + lease_seconds, now, row['id']))
        return self.job(row['id'])

    def bump_attempt(self, job_id: int) -> int:
        with self.tx():
            self.db.execute('UPDATE jobs SET attempts = attempts + 1 WHERE id = ?', (job_id,))
        return self.job(job_id)['attempts']

    def finish(self, job_id: int, now: int) -> None:
        with self.tx():
            self.db.execute(
                "UPDATE jobs SET state = 'done', lease_until = NULL, error = NULL, updated_at = ? "
                'WHERE id = ?', (now, job_id))

    def fail(self, job_id: int, state: str, error: str, now: int) -> None:
        if state not in ('failed_model', 'failed_app'):
            raise ValueError(f'not a failure state: {state!r}')
        with self.tx():
            self.db.execute(
                'UPDATE jobs SET state = ?, lease_until = NULL, error = ?, updated_at = ? '
                'WHERE id = ?', (state, error, now, job_id))

    def requeue(self, job_id: int, now: int) -> None:
        with self.tx():
            self.db.execute(
                "UPDATE jobs SET state = 'queued', attempts = 0, error = NULL, lease_until = NULL, "
                'updated_at = ? WHERE id = ?', (now, job_id))

    def count_by_state(self) -> dict:
        return {r['state']: r['n'] for r in
                self.db.execute('SELECT state, COUNT(*) AS n FROM jobs GROUP BY state')}

    # -- summaries ----------------------------------------------------------
    def save_summary(self, job_id: int, summary: dict, model: str, now: int) -> None:
        """Store the job's summary; a rerun replaces it instead of adding one (D-004)."""
        body = json.dumps(summary, sort_keys=True)
        with self.tx():
            row = self.db.execute('SELECT id FROM summaries WHERE job_id = ? ORDER BY id LIMIT 1',
                                  (job_id,)).fetchone()
            if row is None:
                self.db.execute(
                    'INSERT INTO summaries(job_id, title, body, model, created_at) '
                    'VALUES(?, ?, ?, ?, ?)', (job_id, summary['title'], body, model, now))
            else:
                self.db.execute(
                    'UPDATE summaries SET title = ?, body = ?, model = ?, created_at = ? WHERE id = ?',
                    (summary['title'], body, model, now, row['id']))

    def summaries(self, job_id: int | None = None) -> list[dict]:
        sql = ('SELECT s.*, j.source FROM summaries s JOIN jobs j ON j.id = s.job_id')
        if job_id is None:
            rows = self.db.execute(sql + ' ORDER BY s.job_id, s.id')
        else:
            rows = self.db.execute(sql + ' WHERE s.job_id = ? ORDER BY s.id', (job_id,))
        out = []
        for r in rows:
            d = dict(r)
            d['body'] = json.loads(d['body'])
            out.append(d)
        return out
''',
    'pipeline/worker.py': r'''"""The worker: claims jobs and turns transcripts into validated summaries.

One job, step by step:

    claim -> read archived transcript -> model call (with retries)
          -> parse/validate -> summary row -> export row -> done

Every step after the claim may run again after a crash (D-003), so the writes
are idempotent (D-004). Model failures are retried and end in failed_model;
input problems end in failed_app without a model call (D-006, D-007).
The model sees redacted text only and its output is redacted before it is
stored or exported (D-009).
"""
from __future__ import annotations

import time
from pathlib import Path

from . import export, faults, output, status
from .errors import ModelError, TranscriptError
from .model_client import make_client
from .redact import redact_text, redact_value
from .textutil import mask_email, preview, read_text


class Worker:
    def __init__(self, cfg, store, client=None, sleep=time.sleep, log=print):
        self.cfg = cfg
        self.store = store
        self.client = client or make_client(cfg)
        self.sleep = sleep
        self.log = log

    def run(self, now: int, max_jobs: int | None = None) -> list[tuple[int, str]]:
        """Process claimable jobs until none is left (or max_jobs is reached)."""
        results = []
        while max_jobs is None or len(results) < max_jobs:
            job = self.store.claim(now, self.cfg.lease_seconds)
            if job is None:
                break
            faults.checkpoint('after_claim')
            results.append((job['id'], self.process(job, now)))
        status.write(self.cfg.status_path, status.snapshot(self.store, now))
        return results

    def _prompt(self, job: dict) -> str:
        path = Path(job['transcript_path'])
        try:
            text = read_text(path)
        except OSError as exc:
            raise TranscriptError(f'archive copy unreadable: {exc.__class__.__name__}') from None
        # Archive copies from before D-009 may still hold personal data.
        return output.build_prompt(redact_text(text), self.cfg.max_transcript_chars)

    def process(self, job: dict, now: int) -> str:
        try:
            prompt = self._prompt(job)
        except TranscriptError as exc:
            self.store.fail(job['id'], 'failed_app', redact_text(f'TranscriptError: {exc}'), now)
            self.log(f"job {job['id']} ({job['source']}) needs attention: {exc}")
            return 'failed_app'
        while True:
            attempt = self.store.bump_attempt(job['id'])
            try:
                raw = self.client.complete(prompt, key=job['source'], attempt=attempt)
                faults.checkpoint('after_model')
                summary = redact_value(output.parse_summary(raw))
            except ModelError as exc:
                message = redact_text(f'{type(exc).__name__}: {exc}')
                self.log(f"job {job['id']} attempt {attempt} failed: {mask_email(message)}")
                if attempt >= self.cfg.max_attempts:
                    self.store.fail(job['id'], 'failed_model', message, now)
                    return 'failed_model'
                self.sleep(self.cfg.backoff(attempt))
                continue
            self.store.save_summary(job['id'], summary, self.client.name, now)
            faults.checkpoint('after_summary')
            export.append_row(self.cfg.export_path, job, summary, self.client.name)
            faults.checkpoint('after_export')
            self.store.finish(job['id'], now)
            self.log(f"job {job['id']} ({job['source']}) done: {preview(summary['title'])}")
            return 'done'
''',
    'ui/status.ts': r'''// Ops status page model: reads out/status.json (docs/contracts.md).
// Runtime: node with type stripping (no tsc build step; erasable TypeScript only).

export function padLeft(value: string | number, width: number): string {
  const s = String(value);
  return s.length >= width ? s : ' '.repeat(width - s.length) + s;
}

export function padRight(value: string, width: number): string {
  return value.length >= width ? value : value + ' '.repeat(width - value.length);
}

export function plural(n: number, word: string): string {
  return `${n} ${word}${n === 1 ? '' : 's'}`;
}

export function age(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return '?';
  if (seconds < 60) return `${Math.floor(seconds)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

export interface JobRow {
  id: number;
  source: string;
  state: string;
  attempts: number;
  error: string | null;
  updated_at: number;
  redacted?: boolean; // D-009; absent in snapshots written before the change
}

export interface Snapshot {
  generated_at: number;
  counts: Record<string, number>;
  jobs: JobRow[];
}

export interface Overview {
  total: number;
  pending: number;
  done: number;
  retryable: number;
  attention: number;
}

const LABELS: Record<string, string> = {
  queued: 'waiting',
  running: 'in progress',
  done: 'done',
  failed_model: 'retryable',
  failed_app: 'needs attention',
  failed: 'retryable', // rows from before D-006
};

export function label(state: string): string {
  return LABELS[state] ?? state;
}

export function parseSnapshot(text: string): Snapshot {
  const s = JSON.parse(text);
  if (!s || typeof s !== 'object' || typeof s.counts !== 'object' || s.counts === null) {
    throw new Error('not a status snapshot');
  }
  s.jobs ??= [];
  return s as Snapshot;
}

export function overview(s: Snapshot): Overview {
  const c = s.counts ?? {};
  const n = (k: string): number => c[k] ?? 0;
  const total = Object.values(c).reduce((a, b) => a + b, 0);
  return {
    total,
    pending: n('queued') + n('running'),
    done: n('done'),
    retryable: n('failed_model') + n('failed'),
    attention: n('failed_app'),
  };
}

export function headline(s: Snapshot): string {
  const o = overview(s);
  return `${plural(o.total, 'job')}: ${o.pending} pending, ${o.done} done, ` +
    `${o.retryable} retryable, ${o.attention} need attention`;
}

export function jobLine(j: JobRow, now?: number): string {
  let line = `${padLeft(j.id, 5)}  ${padRight(j.source, 14)} ${label(j.state)}`;
  if (j.attempts > 0) line += ` (${plural(j.attempts, 'attempt')})`;
  if (now !== undefined) line += `, ${age(now - j.updated_at)} ago`;
  if (j.redacted === true) line += ' [redacted]';
  return line;
}

export function render(s: Snapshot): string {
  const lines = [headline(s)];
  for (const j of s.jobs) lines.push(jobLine(j, s.generated_at));
  return lines.join('\n');
}
''',
}

HIDDEN1 = r'''import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LEASE = 300
TRANSCRIPT = ('[00:00:03] Lea: Weekly sync, budget first.\n'
              '[00:00:40] Tomas: Budget agreed, launch moves to May.\n'
              '[00:01:10] Lea: Tomas sends the draft by Friday.\n')


def ok(title='Weekly sync', owner='Tomas', task='Send the draft by Friday'):
    return {'kind': 'ok', 'text': json.dumps({'title': title, 'bullets': ['Budget agreed', 'Launch moves to May'],
                                              'action_items': [{'owner': owner, 'task': task}]})}


class Workspace:
    def __init__(self, test):
        self.test = test
        self.tmp = tempfile.TemporaryDirectory()
        test.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.root = base / 'ws'
        self.responses = base / 'responses'
        (self.root / 'inbox').mkdir(parents=True)
        self.responses.mkdir()
        cfg = {'db_path': 'state/pipeline.db', 'inbox_dir': 'inbox', 'archive_dir': 'archive',
               'export_path': 'out/summaries_v1.tsv', 'status_path': 'out/status.json',
               'calls_log': 'state/model_calls.jsonl', 'responses_dir': str(self.responses),
               'lease_seconds': LEASE, 'max_transcript_chars': 2000,
               'model': {'name': 'stub-summarizer-2', 'max_attempts': 3, 'backoff_seconds': [0, 0, 0]}}
        self.config = self.root / 'pipeline.json'
        self.config.write_text(json.dumps(cfg))

    def drop(self, source, text=TRANSCRIPT):
        (self.root / 'inbox' / f'{source}.txt').write_text(text, encoding='utf-8')

    def inbox(self, source):
        return (self.root / 'inbox' / f'{source}.txt').exists()

    def respond(self, source, default, attempts=None):
        spec = {'default': default}
        if attempts:
            spec['attempts'] = attempts
        (self.responses / f'{source}.json').write_text(json.dumps(spec))

    def cli(self, *args, crash=None):
        env = dict(os.environ)
        env.pop('PIPELINE_CRASH_AT', None)
        if crash:
            env['PIPELINE_CRASH_AT'] = crash
        p = subprocess.run([sys.executable, '-m', 'pipeline.cli', '--config', str(self.config), *args],
                           cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
        expected = 75 if crash else 0
        self.test.assertEqual(p.returncode, expected, f'{args} crash={crash}: {p.stderr[-600:]}')
        return p

    def q(self, sql, *params):
        db = sqlite3.connect(self.root / 'state' / 'pipeline.db')
        try:
            return db.execute(sql, params).fetchall()
        finally:
            db.close()

    def states(self, source):
        return [r[0] for r in self.q('SELECT state FROM jobs WHERE source = ? ORDER BY id', source)]

    def state(self, source):
        states = self.states(source)
        self.test.assertEqual(len(states), 1, f'{source}: expected exactly one job, got {states}')
        return states[0]

    def summaries(self, source):
        return self.q('SELECT s.body FROM summaries s JOIN jobs j ON j.id = s.job_id WHERE j.source = ?', source)

    def export_rows(self, source):
        path = self.root / 'out' / 'summaries_v1.tsv'
        if not path.exists():
            return []
        lines = path.read_text(encoding='utf-8').splitlines()
        return [l for l in lines[1:] if l.split('\t')[1:2] == [source]]

    def calls(self, source):
        path = self.root / 'state' / 'model_calls.jsonl'
        if not path.exists():
            return 0
        return sum(1 for l in path.read_text(encoding='utf-8').splitlines()
                   if l.strip() and json.loads(l).get('key') == source)


class ReliabilityContract(unittest.TestCase):
    # docs/decisions.md D-003 (1): inbox file removed only after the job is committed;
    # docs/operations.md "Crash rehearsal" + pipeline/faults.py checkpoint after_archive.
    def test_crash_during_accept_keeps_the_upload(self):
        ws = Workspace(self)
        ws.drop('call-7001')
        ws.respond('call-7001', ok())
        ws.cli('accept', '--now', '1000', crash='after_archive')
        self.assertTrue(ws.inbox('call-7001'), 'accepted upload vanished after a crash')
        ws.cli('accept', '--now', '1001')
        self.assertFalse(ws.inbox('call-7001'))
        ws.cli('work', '--now', '1002')
        self.assertEqual(ws.state('call-7001'), 'done')
        self.assertEqual(len(ws.summaries('call-7001')), 1)
        self.assertEqual(len(ws.export_rows('call-7001')), 1)

    # docs/decisions.md D-003 (2, 3) lease expiry and no takeover of a live lease;
    # D-004 at most one summary row and one Export v1 row per job;
    # pipeline/faults.py worker checkpoints.
    def test_worker_crash_is_recovered_once(self):
        for step in ('after_claim', 'after_model', 'after_summary', 'after_export'):
            with self.subTest(step=step):
                ws = Workspace(self)
                ws.drop('call-7002')
                ws.respond('call-7002', ok())
                ws.cli('accept', '--now', '1000')
                ws.cli('work', '--now', '1000', crash=step)
                before = (len(ws.summaries('call-7002')), len(ws.export_rows('call-7002')))
                ws.cli('work', '--now', str(1000 + LEASE // 2))
                self.assertEqual(ws.state('call-7002'), 'running', 'a live lease was taken over')
                self.assertEqual((len(ws.summaries('call-7002')), len(ws.export_rows('call-7002'))), before)
                ws.cli('work', '--now', str(1000 + LEASE + 1))
                self.assertEqual(ws.state('call-7002'), 'done')
                self.assertEqual(len(ws.summaries('call-7002')), 1)
                self.assertEqual(len(ws.export_rows('call-7002')), 1)
                ws.cli('work', '--now', str(1000 + 3 * LEASE))
                self.assertEqual(len(ws.summaries('call-7002')), 1)
                self.assertEqual(len(ws.export_rows('call-7002')), 1)

    # docs/decisions.md D-002 one job per source, redelivered inbox file removed;
    # docs/operations.md incident notes 2026-09-11.
    def test_redelivered_upload_is_one_job(self):
        ws = Workspace(self)
        ws.respond('call-7003', ok())
        ws.drop('call-7003')
        ws.cli('accept', '--now', '1000')
        ws.drop('call-7003')
        ws.cli('accept', '--now', '1005')
        self.assertFalse(ws.inbox('call-7003'))
        ws.cli('work', '--now', '1010')
        ws.drop('call-7003')
        ws.cli('accept', '--now', '1020')
        ws.cli('work', '--now', '1030')
        self.assertFalse(ws.inbox('call-7003'))
        self.assertEqual(ws.state('call-7003'), 'done')
        self.assertEqual(len(ws.summaries('call-7003')), 1)
        self.assertEqual(len(ws.export_rows('call-7003')), 1)
        self.assertEqual(ws.calls('call-7003'), 1)

    # docs/decisions.md D-005 (malformed/invalid output is a model failure),
    # D-006 (failed_model vs failed_app, model not called for app failures, attempts = model calls),
    # D-007 (over-long transcripts are failed_app, never truncated).
    def test_model_and_application_failures_are_separated(self):
        ws = Workspace(self)
        cases = {
            'call-7010': ('', ok()),                                   # empty transcript
            'call-7011': ('word ' * 500, ok()),                        # 2500 chars > 2000
            'call-7012': (TRANSCRIPT, {'kind': 'timeout'}),
            'call-7013': (TRANSCRIPT, {'kind': 'ok', 'text': '{"title": "Sync", "bullets": []}'}),
            'call-7014': (TRANSCRIPT, {'kind': 'ok', 'text': 'Sure! Here is the summary you asked for.'}),
        }
        for source, (text, response) in cases.items():
            ws.drop(source, text)
            ws.respond(source, response)
        ws.drop('call-7015')
        ws.respond('call-7015', ok(), attempts=[{'kind': 'rate_limited'}, {'kind': 'timeout'}])
        ws.cli('accept', '--now', '2000')
        ws.cli('work', '--now', '2000')
        expected = {'call-7010': ('failed_app', 0), 'call-7011': ('failed_app', 0),
                    'call-7012': ('failed_model', 3), 'call-7013': ('failed_model', 3),
                    'call-7014': ('failed_model', 3), 'call-7015': ('done', 3)}
        for source, (state, calls) in expected.items():
            with self.subTest(source=source):
                self.assertEqual(ws.state(source), state)
                self.assertEqual(ws.calls(source), calls)
                self.assertEqual(len(ws.summaries(source)), 1 if state == 'done' else 0)
                self.assertEqual(len(ws.export_rows(source)), 1 if state == 'done' else 0)
        attempts = dict(ws.q('SELECT source, attempts FROM jobs'))
        self.assertEqual(attempts['call-7012'], 3)
        self.assertEqual(attempts['call-7015'], 3)

    # docs/decisions.md D-008 (requeue only failed_model; --inline follows worker rules),
    # D-005 (no salvage), D-004; docs/operations.md incident notes 2026-09-02 and 2026-09-10.
    def test_requeue_follows_worker_rules(self):
        ws = Workspace(self)
        ws.drop('call-7020')
        ws.respond('call-7020', {'kind': 'timeout'})
        ws.drop('call-7021', '')
        ws.respond('call-7021', ok())
        ws.cli('accept', '--now', '3000')
        ws.cli('work', '--now', '3000')
        self.assertEqual(ws.state('call-7020'), 'failed_model')
        self.assertEqual(ws.state('call-7021'), 'failed_app')
        ws.respond('call-7020', {'kind': 'ok', 'text': 'Sure! Here is the summary you asked for: budget agreed.'})
        ws.cli('requeue', '--inline', '--now', '3100')
        self.assertEqual(ws.state('call-7020'), 'failed_model')
        self.assertEqual(ws.summaries('call-7020'), [])
        self.assertEqual(ws.export_rows('call-7020'), [])
        self.assertEqual(ws.state('call-7021'), 'failed_app')
        ws.respond('call-7020', ok())
        ws.cli('requeue', '--now', '3200')
        self.assertEqual(ws.state('call-7020'), 'queued')
        self.assertEqual(ws.q("SELECT attempts FROM jobs WHERE source = 'call-7020'"), [(0,)])
        ws.cli('work', '--now', '3200')
        ws.cli('requeue', '--inline', '--now', '3300')
        self.assertEqual(ws.state('call-7020'), 'done')
        self.assertEqual(len(ws.summaries('call-7020')), 1)
        self.assertEqual(len(ws.export_rows('call-7020')), 1)
        self.assertEqual(ws.state('call-7021'), 'failed_app')
        self.assertEqual(ws.calls('call-7021'), 0)

    # docs/contracts.md part 2 "status.json": exactly the five states as count keys,
    # jobs[].state is the real stored state.
    def test_status_snapshot_reports_real_states(self):
        ws = Workspace(self)
        ws.drop('call-7030'); ws.respond('call-7030', ok())
        ws.drop('call-7031'); ws.respond('call-7031', {'kind': 'rate_limited'})
        ws.drop('call-7032', ''); ws.respond('call-7032', ok())
        ws.cli('accept', '--now', '4000')
        ws.cli('work', '--now', '4000')
        ws.drop('call-7033'); ws.respond('call-7033', ok())
        ws.cli('accept', '--now', '4010')
        ws.cli('status', '--now', '4020')
        snap = json.loads((ws.root / 'out' / 'status.json').read_text(encoding='utf-8'))
        self.assertEqual(snap['counts'], {'queued': 1, 'running': 0, 'done': 1, 'failed_model': 1, 'failed_app': 1})
        self.assertEqual({j['source']: j['state'] for j in snap['jobs']},
                         {'call-7030': 'done', 'call-7031': 'failed_model', 'call-7032': 'failed_app',
                          'call-7033': 'queued'})

    # docs/contracts.md part 2 "UI (ui/status.ts)": labels, overview fields, headline wording.
    def test_status_page_separates_failure_kinds(self):
        snap = {'generated_at': 50, 'counts': {'queued': 2, 'running': 1, 'done': 4, 'failed_model': 3, 'failed_app': 1},
                'jobs': []}
        code = ("import {overview, label, headline} from './ui/status.ts'; const s = %s; "
                "console.log(JSON.stringify([overview(s), ['queued','running','done','failed_model','failed_app'].map(label), headline(s)]))"
                % json.dumps(snap))
        p = subprocess.run(['node', '--experimental-strip-types', '--no-warnings', '--input-type=module', '-e', code],
                           cwd=REPO, capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stderr)
        view, labels, head = json.loads(p.stdout)
        self.assertEqual({k: view.get(k) for k in ('total', 'pending', 'done', 'retryable', 'attention')},
                         {'total': 11, 'pending': 3, 'done': 4, 'retryable': 3, 'attention': 1})
        self.assertEqual(labels, ['waiting', 'in progress', 'done', 'retryable', 'needs attention'])
        self.assertEqual(head, '11 jobs: 3 pending, 4 done, 3 retryable, 1 need attention')
'''

HIDDEN2 = HIDDEN1 + r'''

PII_TRANSCRIPT = ('[00:00:04] Mira: Welcome. Ticket TCK-2024-00017 is open since 2026-09-14.\n'
                  '[00:00:31] Jon: Send the notes to anna.keller@example.org, cc ops-team+calls@mail.example.com.\n'
                  '[00:01:02] Mira: Reach me at +41 00 555 01 23 or on the desk line 044 555 01 99.\n'
                  '[00:01:25] Jon: My old number 079/555 12 34 is gone.\n'
                  '[00:01:40] Jon: Budget stays at 12 500 for 3 sprints, review at 10:30.\n')
REDACTED_TRANSCRIPT = ('[00:00:04] Mira: Welcome. Ticket TCK-2024-00017 is open since 2026-09-14.\n'
                       '[00:00:31] Jon: Send the notes to [EMAIL], cc [EMAIL].\n'
                       '[00:01:02] Mira: Reach me at [PHONE] or on the desk line [PHONE].\n'
                       '[00:01:25] Jon: My old number [PHONE] is gone.\n'
                       '[00:01:40] Jon: Budget stays at 12 500 for 3 sprints, review at 10:30.\n')
RAW_PII = ['anna.keller@example.org', 'ops-team+calls@mail.example.com', '+41 00 555 01 23',
           '044 555 01 99', '079/555 12 34', 'anna.keller', 'ops-team+calls', '555 01 23', '555 01 99']
PII_RESPONSE = ok(owner='anna.keller@example.org', task='Call Mira on +41 00 555 01 23 about the budget')

ORIGINAL_SCHEMA = """
CREATE TABLE jobs(id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT NOT NULL, transcript_path TEXT NOT NULL,
  state TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, lease_until INTEGER, error TEXT,
  accepted_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
CREATE INDEX jobs_state ON jobs(state);
CREATE INDEX jobs_source ON jobs(source);
CREATE TABLE summaries(id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL REFERENCES jobs(id),
  title TEXT NOT NULL, body TEXT NOT NULL, model TEXT NOT NULL, created_at INTEGER NOT NULL);
CREATE INDEX summaries_job ON summaries(job_id);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
INSERT INTO meta VALUES('schema_version', '3');
"""


def node_json(test, code):
    p = subprocess.run(['node', '--experimental-strip-types', '--no-warnings', '--input-type=module', '-e', code],
                       cwd=REPO, capture_output=True, text=True, timeout=30)
    test.assertEqual(p.returncode, 0, p.stderr)
    return json.loads(p.stdout)


class RedactionContract(unittest.TestCase):
    # Stage-2 request (nothing personal written anywhere: database, archive, export, model log)
    # + docs/decisions.md D-009 scope (model output redacted too); crash rehearsal per docs/operations.md.
    def test_nothing_persisted_contains_personal_data(self):
        ws = Workspace(self)
        ws.drop('call-7101', PII_TRANSCRIPT)
        ws.respond('call-7101', PII_RESPONSE)
        ws.cli('accept', '--now', '5000', crash='after_archive')
        ws.cli('accept', '--now', '5001')
        ws.cli('work', '--now', '5002', crash='after_summary')
        ws.cli('work', '--now', str(5002 + LEASE + 1))
        ws.cli('status', '--now', '6000')
        self.assertEqual(ws.state('call-7101'), 'done')
        scanned = 0
        for path in sorted(ws.root.rglob('*')):
            if not path.is_file() or path == ws.config:
                continue
            data = path.read_bytes()
            scanned += 1
            for raw in RAW_PII:
                self.assertNotIn(raw.encode(), data, f'{raw!r} persisted in {path.relative_to(ws.root)}')
        self.assertGreaterEqual(scanned, 4)
        body = json.loads(ws.summaries('call-7101')[0][0])
        self.assertEqual(body['action_items'], [{'owner': '[EMAIL]', 'task': 'Call Mira on [PHONE] about the budget'}])

    # docs/decisions.md D-009 shapes: e-mail and phone patterns, tokens, and the non-matches
    # (timestamps, dates, ticket IDs, amounts); docs/operations.md archive copy.
    def test_archive_copy_is_redacted_precisely(self):
        ws = Workspace(self)
        ws.drop('call-7102', PII_TRANSCRIPT)
        ws.respond('call-7102', ok())
        ws.cli('accept', '--now', '5000')
        self.assertEqual((ws.root / 'archive' / 'call-7102.txt').read_text(encoding='utf-8'), REDACTED_TRANSCRIPT)

    # D-009 "Status" bullet + stage-2 request (status page shows per job whether it was redacted);
    # docs/contracts.md part 2 for the jobLine shape of older snapshots.
    def test_status_reports_redaction_per_job(self):
        ws = Workspace(self)
        ws.drop('call-7103', PII_TRANSCRIPT)
        ws.respond('call-7103', ok())
        ws.drop('call-7104')
        ws.respond('call-7104', ok())
        ws.cli('accept', '--now', '5000')
        ws.cli('work', '--now', '5000')
        ws.cli('status', '--now', '5010')
        snap = json.loads((ws.root / 'out' / 'status.json').read_text(encoding='utf-8'))
        self.assertEqual({j['source']: j.get('redacted') for j in snap['jobs']},
                         {'call-7103': True, 'call-7104': False})
        rows = [dict(j, redacted=True) for j in snap['jobs'][:1]] + [dict(snap['jobs'][0], redacted=False)]
        legacy = {k: v for k, v in snap['jobs'][0].items() if k != 'redacted'}
        code = ("import {jobLine} from './ui/status.ts'; const rows = %s; "
                "console.log(JSON.stringify(rows.map(r => jobLine(r))))" % json.dumps(rows + [legacy]))
        with_flag, without_flag, old = node_json(self, code)
        self.assertTrue(with_flag.endswith(' [redacted]'), with_flag)
        self.assertNotIn('[redacted]', without_flag)
        self.assertNotIn('[redacted]', old)
        self.assertEqual(with_flag, without_flag + ' [redacted]')
        self.assertEqual(old, without_flag)

    # docs/contracts.md "Export v1 (frozen)" + stage-2 request (old export format stays);
    # docs/operations.md `export --rebuild`.
    def test_export_v1_format_is_unchanged(self):
        ws = Workspace(self)
        ws.drop('call-7105', PII_TRANSCRIPT)
        ws.respond('call-7105', PII_RESPONSE)
        ws.drop('call-7106')
        ws.respond('call-7106', ok(owner='Lea', task='Book the room'))
        ws.cli('accept', '--now', '5000')
        ws.cli('work', '--now', '5000')
        path = ws.root / 'out' / 'summaries_v1.tsv'
        content = path.read_text(encoding='utf-8')
        lines = content.split('\n')
        self.assertEqual(lines[-1], '')
        self.assertEqual(lines[0], 'job_id\tsource\ttitle\tbullets\taction_items\tmodel')
        self.assertTrue(all(len(line.split('\t')) == 6 for line in lines[:-1]))
        rows = {line.split('\t')[1]: line.split('\t') for line in lines[1:-1]}
        ids = dict(ws.q('SELECT source, id FROM jobs'))
        self.assertEqual(rows['call-7105'], [str(ids['call-7105']), 'call-7105', 'Weekly sync',
                                             'Budget agreed | Launch moves to May',
                                             '[EMAIL]: Call Mira on [PHONE] about the budget', 'stub-summarizer-2'])
        self.assertEqual(rows['call-7106'][4], 'Lea: Book the room')
        path.unlink()
        ws.cli('export', '--rebuild')
        self.assertEqual(path.read_text(encoding='utf-8'), content)

    # docs/operations.md "Schema changes" (automatic, additive, old rows keep working)
    # + D-009 "Jobs accepted before the change are false".
    def test_existing_database_is_migrated_in_place(self):
        ws = Workspace(self)
        (ws.root / 'state').mkdir()
        (ws.root / 'archive').mkdir()
        (ws.root / 'archive' / 'call-0001.txt').write_text('[00:00:01] Old call.\n', encoding='utf-8')
        db = sqlite3.connect(ws.root / 'state' / 'pipeline.db')
        db.executescript(ORIGINAL_SCHEMA)
        db.execute("INSERT INTO jobs VALUES(1, 'call-0001', ?, 'done', 1, NULL, NULL, 10, 10)",
                   (str(ws.root / 'archive' / 'call-0001.txt'),))
        db.execute("INSERT INTO summaries VALUES(1, 1, 'Old call', ?, 'stub-summarizer-1', 10)",
                   (json.dumps({'title': 'Old call', 'bullets': ['x'], 'action_items': []}),))
        db.commit()
        db.close()
        ws.drop('call-7107', PII_TRANSCRIPT)
        ws.respond('call-7107', ok())
        ws.cli('accept', '--now', '5000')
        ws.cli('work', '--now', '5000')
        ws.cli('status', '--now', '5010')
        snap = json.loads((ws.root / 'out' / 'status.json').read_text(encoding='utf-8'))
        self.assertEqual({j['source']: (j['state'], j.get('redacted')) for j in snap['jobs']},
                         {'call-0001': ('done', False), 'call-7107': ('done', True)})
        self.assertEqual(ws.q("SELECT title FROM summaries WHERE job_id = 1"), [('Old call',)])
        self.assertEqual(ws.q("SELECT COUNT(*) FROM jobs"), [(2,)])
'''

STAGE1 = 'Make the transcript pipeline reliable, we lose things sometimes. Uploads that never turn up, calls that appear twice in the report, a garbage summary that reached a customer, and ops say the status page never shows them anything useful. I thought we had settled all of this ages ago.'

STAGE2 = "Change of plan on personal data: legal approved the redaction proposal, and they want phone numbers covered too, not just email addresses. From now on nothing personal may be written anywhere by the pipeline: database, archive, export, model log, anything. Ops also want to see per job on the status page whether something was redacted. The reporting team's importer must keep working on the export exactly as it is, and everything from the reliability work has to keep holding."

OWNER_FACTS = {
    'decision_log': 'docs/decisions.md is authoritative; a later entry wins over older code comments.',
    'failure_states': 'Use failed_model and failed_app exactly as D-006 describes; nothing else changes the UI contract.',
    'redaction': 'Stage 2: D-009 as written, with phone numbers in scope using its phone shape and the [EMAIL]/[PHONE] tokens.',
    'export': 'Export v1 stays exactly as documented: same header, same six columns, same joins.',
}


def build():
    p = project('ho04_pipeline', 'ai_data', 1 / 6, ['Python', 'TypeScript', 'JSON', 'SQLite', 'Bash'],
                FILES, VISIBLE, [STAGE1, STAGE2], [REFERENCE1, REFERENCE2], [HIDDEN1, HIDDEN2],
                restart_after_first=True, owner_facts=OWNER_FACTS)
    p.update(difficulty='ultra', cluster='ai_pipeline_reliability', predicted_single_pass=[.05, .30],
             budget_seconds=1800)
    return p
