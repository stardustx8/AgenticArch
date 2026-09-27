"""Ultra backup/rotation/restore project (synthetic). Bash entry points, Python helpers, JSON config.

Stage 1 hides four cross-component defects, each present in two places (bash and Python):
retention calendar logic (fixed UTC offset + %W weeks; bash meta.local_date and Python fallback),
the run lock (per-command pid files in bash, pid file in Python gc; decision D-010 wants one
shared flock), restore verification (restore merges, verify ignores unexpected files), and
interrupted runs (EXIT trap seals partial copies; seal ignores plan.json; completeness ignores meta).
Stage 2 changes the retention counts, adds a yearly tier and a lock-free rotate --dry-run.
"""
from tools.ho02_projects import project


def sub(text, old, new, count=1):
    if text.count(old) != count:
        raise AssertionError(f'expected {count} occurrence(s) of {old!r}')
    return text.replace(old, new)


# --------------------------------------------------------------------------- repo files

README = r'''# snapkeep

Snapshot backups for the shared project folder on the office NAS: one snapshot per night,
grandfather-father-son rotation, verified restores, and an offsite push.

    bin/backup.sh   [--config FILE] [--quiet]
    bin/rotate.sh   [--config FILE] [-n DAILY] [--quiet]
    bin/restore.sh  [--config FILE] [--replace] [--quiet] <snapshot-id|latest> <target>
    bin/status.sh   [--config FILE] [--json]

The bash entry points do the orchestration; `python3 -m snapkeep` holds the helpers
(scan, copy, seal, plan, verify, gc). See docs/cli.md for flags and exit codes,
docs/snapshot-format.md for the on-disk layout and docs/decisions.md for why things are the
way they are. Operational notes: docs/operations.md. Incidents: docs/incidents.md.

Run the tests with `python3 -m unittest discover -s tests -t .` from this directory. They
create everything under temporary directories; nothing touches /srv or the network.
'''

CONFIG_JSON = r'''{
  "root": "/srv/snapkeep",
  "source": "/srv/share/projects",
  "timezone": "Europe/Zurich",
  "utc_offset_hours": 1,
  "retention": {"daily": 7, "weekly": 4, "monthly": 6},
  "exclude": ["*.tmp", ".cache", "~$*"],
  "verify_after_backup": true,
  "partial_grace_hours": 24
}
'''

COMMON_SH = r'''# shellcheck shell=bash
# Shared helpers for the snapkeep entry scripts. Sourced, not executed.

APP="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
QUIET=0

log() { [ "$QUIET" = 1 ] || printf 'snapkeep: %s\n' "$*" >&2; }
warn() { printf 'snapkeep: warning: %s\n' "$*" >&2; }
die() {
  local code=$1
  shift
  printf 'snapkeep: error: %s\n' "$*" >&2
  exit "$code"
}

# Python helpers live in the snapkeep package next to bin/.
snk() { PYTHONPATH="$APP${PYTHONPATH:+:$PYTHONPATH}" python3 -m snapkeep "$@"; }

# load_config [FILE]: --config wins over SNAPKEEP_CONFIG, which wins over the shipped file.
# Sets ROOT and SNAPDIR and exports SNAPKEEP_CONFIG for the Python helpers.
load_config() {
  export SNAPKEEP_CONFIG="${1:-${SNAPKEEP_CONFIG:-$APP/config/snapkeep.json}}"
  [ -f "$SNAPKEEP_CONFIG" ] || die 2 "config not found: $SNAPKEEP_CONFIG"
  ROOT="$(snk config-get root)" || die 2 "invalid config: $SNAPKEEP_CONFIG"
  SNAPDIR="$ROOT/snapshots"
  mkdir -p "$SNAPDIR"
}

# --- run lock (D-002) -------------------------------------------------------------
# One pid file per command under the root. A lock whose pid is gone is stale and is
# taken over, so a crashed run never blocks the next night.
LOCKFILE=""
acquire_lock() {
  LOCKFILE="$ROOT/.$1.lock"
  if [ -f "$LOCKFILE" ]; then
    local pid
    pid="$(cat "$LOCKFILE" 2>/dev/null || true)"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      die 73 "$1 already running (pid $pid)"
    fi
    log "taking over stale $1 lock (pid ${pid:-unknown})"
  fi
  echo "$$" > "$LOCKFILE"
}

release_lock() {
  if [ -n "$LOCKFILE" ] && [ "$(cat "$LOCKFILE" 2>/dev/null)" = "$$" ]; then
    rm -f "$LOCKFILE"
  fi
}
'''

LOCK_SH = r'''# shellcheck shell=bash
# flock(1)-based run lock. with_lock ROOT opens <root>/.snapkeep.lock on fd 9 and takes an
# exclusive lock that lasts until the process exits (the fd is closed by the kernel, so a
# crashed run can never leave a stale lock behind). Exits 73 when someone else holds it.
with_lock() {
  local file="$1/.snapkeep.lock"
  exec 9>>"$file" || die 73 "cannot open lock file $file"
  flock -n 9 || die 73 "another snapkeep run holds $file"
}
'''

DATES_SH = r'''# shellcheck shell=bash
# Date helpers for the entry scripts. The Python side has its own copy in
# snapkeep/timeutil.py; keep the two in step.

# Clock reading for this run. SNAPKEEP_NOW (epoch seconds) replays a given night.
now_epoch() { printf '%s\n' "${SNAPKEEP_NOW:-$(date +%s)}"; }

# epoch -> snapshot id (UTC, D-001)
snap_id() { date -u -d "@$1" +%Y%m%dT%H%M%SZ; }

# epoch -> local calendar date recorded as meta.json local_date
local_date_of() {
  # The NAS image has no zoneinfo (D-004): apply the configured offset by hand.
  local off
  off="$(snk config-get utc_offset_hours)"
  date -u -d "@$(( $1 + off * 3600 ))" +%F
}

# snapshot id -> epoch
id_epoch() {
  local id=$1
  date -u -d "${id:0:4}-${id:4:2}-${id:6:2} ${id:9:2}:${id:11:2}:${id:13:2}" +%s
}

# whole days between two epochs; only the 2025 cron wrapper still calls this
days_between() { echo $(( ($2 - $1) / 86400 )); }
'''

BACKUP_SH = r'''#!/usr/bin/env bash
# Create one snapshot of the configured source under <root>/snapshots.
# usage: backup.sh [--config FILE] [--quiet]
set -euo pipefail
. "$(dirname "$0")/../lib/common.sh"
. "$APP/lib/dates.sh"

config=""
while [ $# -gt 0 ]; do
  case "$1" in
    --config) [ $# -ge 2 ] || die 2 "--config needs a file"; config=$2; shift 2 ;;
    --quiet) QUIET=1; shift ;;
    -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
    *) die 2 "unknown argument: $1" ;;
  esac
done

load_config "$config"
acquire_lock backup

now="$(now_epoch)"
id="$(snap_id "$now")"
ldate="$(local_date_of "$now")"
staging="$SNAPDIR/$id.partial"
[ ! -e "$SNAPDIR/$id" ] || die 1 "snapshot $id already exists"
[ ! -e "$staging" ] || die 1 "staging directory $staging already exists"

finish() {
  local rc=$?
  if [ -n "$staging" ] && [ -d "$staging" ]; then
    # 2025-12: a run killed by the NAS watchdog left nothing restorable for two nights.
    # Seal whatever was copied so there is always a recent snapshot to restore from.
    if snk seal "$staging" --id "$id" --local-date "$ldate" >/dev/null 2>&1; then
      mv "$staging" "$SNAPDIR/$id"
      warn "run ended early (status $rc); sealed $id with the files copied so far"
    fi
  fi
  release_lock
  exit "$rc"
}
trap finish EXIT
trap 'exit 75' INT TERM

mkdir -p "$staging/data"
snk scan > "$staging/plan.json"
log "copying $(snk count "$staging/plan.json") files into $id"
snk copy "$staging"
snk seal "$staging" --id "$id" --local-date "$ldate" >/dev/null
mv "$staging" "$SNAPDIR/$id"
staging=""
log "sealed $id ($ldate)"

if [ "$(snk config-get verify_after_backup)" = "true" ]; then
  snk verify "$SNAPDIR/$id" "$SNAPDIR/$id/data" || die 3 "post-backup verification failed for $id"
fi
'''

ROTATE_SH = r'''#!/usr/bin/env bash
# Apply the retention policy (docs/decisions.md D-005): delete the complete snapshots
# that the plan does not keep.
# usage: rotate.sh [--config FILE] [-n DAILY] [--quiet]
set -euo pipefail
. "$(dirname "$0")/../lib/common.sh"

config=""
daily=""
while [ $# -gt 0 ]; do
  case "$1" in
    --config) [ $# -ge 2 ] || die 2 "--config needs a file"; config=$2; shift 2 ;;
    -n) [ $# -ge 2 ] || die 2 "-n needs a number"; daily=$2; shift 2 ;;
    --quiet) QUIET=1; shift ;;
    -h|--help) sed -n '2,4p' "$0"; exit 0 ;;
    *) die 2 "unknown argument: $1" ;;
  esac
done
if [ -n "$daily" ] && ! [[ "$daily" =~ ^[0-9]+$ ]]; then
  die 2 "-n needs a number"
fi

load_config "$config"
acquire_lock rotate
trap release_lock EXIT

args=(plan)
[ -z "$daily" ] || args+=(--daily "$daily")
plan="$(snk "${args[@]}")" || die 1 "could not compute the retention plan"

kept=0
deleted=0
while read -r action id _; do
  case "$action" in
    keep) kept=$((kept + 1)) ;;
    delete)
      [[ "$id" =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || die 1 "refusing to delete unexpected name: $id"
      rm -rf -- "${SNAPDIR:?}/$id"
      deleted=$((deleted + 1))
      log "deleted $id" ;;
    ignore) log "ignoring $id (not a complete snapshot)" ;;
  esac
done <<< "$plan"
log "kept $kept, deleted $deleted"
'''

RESTORE_SH = r'''#!/usr/bin/env bash
# Restore a snapshot into a target directory and verify the result (docs/runbook-restore.md).
# usage: restore.sh [--config FILE] [--replace] [--quiet] <snapshot-id|latest> <target>
set -euo pipefail
. "$(dirname "$0")/../lib/common.sh"
. "$APP/lib/lock.sh"

config=""
replace=0
pos=()
while [ $# -gt 0 ]; do
  case "$1" in
    --config) [ $# -ge 2 ] || die 2 "--config needs a file"; config=$2; shift 2 ;;
    --replace) replace=1; shift ;;
    --quiet) QUIET=1; shift ;;
    -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
    -*) die 2 "unknown argument: $1" ;;
    *) pos+=("$1"); shift ;;
  esac
done
[ "${#pos[@]}" -eq 2 ] || die 2 "usage: restore.sh [--config FILE] [--replace] <snapshot-id|latest> <target>"
ref=${pos[0]}
target=${pos[1]}

load_config "$config"
with_lock "$ROOT"

snap="$(snk resolve "$ref")" || die 2 "no complete snapshot matches '$ref'"
mkdir -p "$target"
if [ -n "$(ls -A "$target")" ] && [ "$replace" != 1 ]; then
  die 4 "target $target is not empty (use --replace to restore over it)"
fi

# --replace: the snapshot's files are copied over whatever is already there
cp -a "$snap/data/." "$target/"

snk verify "$snap" "$target" || die 3 "verification failed: $target does not match $(basename "$snap")"
log "restored $(basename "$snap") into $target"
'''

STATUS_SH = r'''#!/usr/bin/env bash
# Print a short summary of the snapshot store.
# usage: status.sh [--config FILE] [--json]
set -euo pipefail
. "$(dirname "$0")/../lib/common.sh"

config=""
fmt=()
while [ $# -gt 0 ]; do
  case "$1" in
    --config) [ $# -ge 2 ] || die 2 "--config needs a file"; config=$2; shift 2 ;;
    --json) fmt=(--json); shift ;;
    -h|--help) sed -n '2,3p' "$0"; exit 0 ;;
    *) die 2 "unknown argument: $1" ;;
  esac
done
load_config "$config"
snk status "${fmt[@]}"
'''

OFFSITE_SH = r'''#!/usr/bin/env bash
# Nightly offsite push, run on the NAS at 03:15 after backup.sh and rotate.sh.
# The real transfer lives in the NAS image; this copy documents the contract with snapkeep.
# It holds the snapkeep flock for the whole transfer so rotate cannot delete the snapshot
# being pushed (D-010). Offsite folders are named by the snapshot's meta.json local_date.
set -euo pipefail
root=${1:?usage: offsite-sync.sh ROOT DEST}
dest=${2:?usage: offsite-sync.sh ROOT DEST}
app="$(cd "$(dirname "$0")/.." && pwd)"

exec 9>>"$root/.snapkeep.lock"
flock -w 3600 9

latest="$(PYTHONPATH="$app" python3 -m snapkeep resolve latest)"
day="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["local_date"])' "$latest/meta.json")"
echo "would push $(basename "$latest") to $dest/$day"
'''

CRON = r'''# snapkeep on the office NAS (crontab of user backup; times are NAS local time)
# m  h  dom mon dow  command
30   0  *   *   *    /opt/snapkeep/bin/backup.sh --quiet && /opt/snapkeep/bin/rotate.sh --quiet
15   3  *   *   *    /opt/snapkeep/contrib/offsite-sync.sh /srv/snapkeep offsite:/snapkeep
0    5  *   *   0    cd /opt/snapkeep && python3 -m snapkeep gc
# The wrapper that alerts on exit codes (see docs/operations.md) is the NAS's job runner,
# which wraps each line; exit 73 means "skipped, retry in 10 minutes".
'''

INIT_PY = r'''"""snapkeep: snapshot backups with GFS rotation. Bash entry points live in bin/."""
__version__ = '1.4.2'
'''

MAIN_PY = r'''from snapkeep.cli import main

raise SystemExit(main())
'''

CONFIG_PY = r'''"""Configuration loading.

config/snapkeep.json is the shipped configuration. Hosts deployed before 2026-02 have no
retention block, or only part of one, and fall back to DEFAULTS tier by tier, so DEFAULTS
must always equal the shipped file (D-011).
"""
import json
import os
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
SHIPPED = APP / 'config' / 'snapkeep.json'

TIERS = ('daily', 'weekly', 'monthly')

DEFAULTS = {
    'timezone': 'Europe/Zurich',
    'utc_offset_hours': 1,
    'retention': {'daily': 7, 'weekly': 4, 'monthly': 6},
    'exclude': [],
    'verify_after_backup': True,
    'partial_grace_hours': 24,
}


class ConfigError(ValueError):
    pass


def load(path=None):
    path = Path(path or os.environ.get('SNAPKEEP_CONFIG') or SHIPPED)
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        raise ConfigError(f'config not found: {path}') from None
    except ValueError as exc:
        raise ConfigError(f'config is not valid JSON: {path}: {exc}') from None
    if not isinstance(data, dict):
        raise ConfigError('config must be a JSON object')
    cfg = json.loads(json.dumps(DEFAULTS))
    for key, value in data.items():
        if key == 'retention':
            if not isinstance(value, dict):
                raise ConfigError('retention must be an object')
            cfg['retention'] = dict(DEFAULTS['retention'], **value)
        else:
            cfg[key] = value
    for key in ('root', 'source'):
        if not isinstance(cfg.get(key), str) or not cfg[key]:
            raise ConfigError(f'missing {key}')
    for tier, count in cfg['retention'].items():
        if tier not in TIERS:
            raise ConfigError(f'unknown retention tier: {tier}')
        if type(count) is not int or count < 0:
            raise ConfigError(f'retention.{tier} must be a non-negative integer')
    return cfg


def get(cfg, dotted):
    value = cfg
    for part in dotted.split('.'):
        value = value[part]
    return value
'''

TIMEUTIL_PY = r'''"""Time helpers for the Python side. lib/dates.sh is the bash copy; keep them in step."""
import os
import re
import time
from datetime import date, datetime, timedelta, timezone

ID_FORMAT = '%Y%m%dT%H%M%SZ'
_ID = re.compile(r'^\d{8}T\d{6}Z$')


def is_id(text):
    return bool(_ID.match(text))


def parse_id(snap_id):
    """Snapshot id -> aware UTC datetime (ids are UTC, D-001)."""
    return datetime.strptime(snap_id, ID_FORMAT).replace(tzinfo=timezone.utc)


def id_from_epoch(epoch):
    return datetime.fromtimestamp(int(epoch), timezone.utc).strftime(ID_FORMAT)


def id_epoch(snap_id):
    return int(parse_id(snap_id).timestamp())


def now_epoch():
    raw = os.environ.get('SNAPKEEP_NOW')
    return int(raw) if raw else int(time.time())


def local_date(snap_id, cfg):
    """Local calendar date of a snapshot, for snapshots whose meta has no local_date."""
    # The NAS image ships without zoneinfo, so apply the configured offset (D-004).
    offset = timedelta(hours=cfg.get('utc_offset_hours', 1))
    return (parse_id(snap_id) + offset).date()


def parse_date(text):
    return date.fromisoformat(text)
'''

SNAPSHOTS_PY = r'''"""Snapshot discovery. Layout and the completeness rule: docs/snapshot-format.md."""
import json
from pathlib import Path

from snapkeep import timeutil

SUFFIX = '.partial'


def _read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, NotADirectoryError, ValueError):
        return {}


class Snapshot:
    def __init__(self, path):
        self.path = Path(path)
        name = self.path.name
        self.partial = name.endswith(SUFFIX)
        self.id = name[:-len(SUFFIX)] if self.partial else name
        self.meta = _read_json(self.path / 'meta.json')

    @property
    def complete(self):
        # The rename out of <id>.partial is the commit point (D-006).
        return not self.partial

    def local_date(self, cfg):
        recorded = self.meta.get('local_date')
        if recorded:
            return timeutil.parse_date(recorded)
        return timeutil.local_date(self.id, cfg)

    def __repr__(self):
        return f'Snapshot({self.path.name!r})'


def snapshot_dir(cfg):
    return Path(cfg['root']) / 'snapshots'


def list_all(cfg):
    base = snapshot_dir(cfg)
    if not base.is_dir():
        return []
    found = []
    for path in sorted(base.iterdir()):
        name = path.name[:-len(SUFFIX)] if path.name.endswith(SUFFIX) else path.name
        if path.is_dir() and timeutil.is_id(name):
            found.append(Snapshot(path))
    return found


def latest(cfg):
    done = [s for s in list_all(cfg) if s.complete]
    return max(done, key=lambda s: s.id) if done else None


def resolve(cfg, ref):
    if ref == 'latest':
        return latest(cfg)
    for snap in list_all(cfg):
        if snap.id == ref and snap.complete:
            return snap
    return None
'''

MANIFEST_PY = r'''"""Manifests: size and sha256 of every file in a snapshot's data/ tree."""
import fnmatch
import hashlib
import json
import os
from pathlib import Path

VERSION = 1


def excluded(rel, patterns):
    parts = rel.split('/')
    return any(fnmatch.fnmatchcase(part, pat) for part in parts for pat in patterns)


def scan(root, exclude=()):
    """Sorted relative paths (posix) of the regular files under root; symlinks are skipped."""
    root = Path(root)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_symlink() or not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if not excluded(rel, exclude):
                out.append(rel)
    return sorted(out)


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 16), b''):
            h.update(block)
    return h.hexdigest()


def build(data_dir, paths=None):
    data_dir = Path(data_dir)
    paths = scan(data_dir) if paths is None else paths
    files = {}
    for rel in paths:
        p = data_dir / rel
        files[rel] = {'size': p.stat().st_size, 'sha256': digest(p)}
    return {'version': VERSION, 'files': files}


def write(path, doc):
    Path(path).write_text(json.dumps(doc, indent=1, sort_keys=True) + '\n')


def read(path):
    doc = json.loads(Path(path).read_text())
    if doc.get('version') != VERSION:
        raise ValueError(f'unsupported manifest version in {path}')
    return doc
'''

COPIER_PY = r'''"""Copies the planned files from the source into a staging tree (D-003)."""
import json
import os
import shutil
from pathlib import Path


class Interrupted(Exception):
    """The copy stopped before its final flush (fault injection or a signal)."""


def fail_after():
    raw = os.environ.get('SNAPKEEP_FAIL_AFTER', '')
    return int(raw) if raw.strip() else None


def _flush(dest):
    for dirpath, _dirs, _files in os.walk(dest):
        fd = os.open(dirpath, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def copy_tree(source, staging, files, stop_after=None):
    """Copy files (relative paths) from source into staging/data.

    A file that vanishes between the scan and the copy is recorded in staging/vanished.json;
    the next night picks up the change.
    """
    source, staging = Path(source), Path(staging)
    data = staging / 'data'
    copied, vanished = 0, []
    if stop_after == 0:
        raise Interrupted('stopped before the first file')
    for rel in files:
        target = data / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source / rel, target)
        except FileNotFoundError:
            vanished.append(rel)
            continue
        copied += 1
        if stop_after is not None and copied >= stop_after:
            raise Interrupted(f'stopped after {copied} files')
    if vanished:
        (staging / 'vanished.json').write_text(json.dumps(vanished) + '\n')
    _flush(data)
    return copied
'''

STAGING_PY = r'''"""Staging directories: plan.json before the copy, manifest.json and meta.json at seal time."""
import json
from pathlib import Path

from snapkeep import manifest, timeutil


class Incomplete(Exception):
    pass


def write_plan(cfg):
    files = manifest.scan(cfg['source'], cfg.get('exclude', []))
    return {'source': cfg['source'], 'files': files}


def read_plan(staging):
    return json.loads((Path(staging) / 'plan.json').read_text())


def vanished(staging):
    path = Path(staging) / 'vanished.json'
    return json.loads(path.read_text()) if path.exists() else []


def seal(staging, snap_id, local_date):
    """Write manifest.json and meta.json (status complete) into a staging directory."""
    staging = Path(staging)
    doc = manifest.build(staging / 'data')
    manifest.write(staging / 'manifest.json', doc)
    meta = {
        'id': snap_id,
        'local_date': local_date,
        'status': 'complete',
        'files': len(doc['files']),
        'sealed_at': timeutil.id_from_epoch(timeutil.now_epoch()),
    }
    (staging / 'meta.json').write_text(json.dumps(meta, indent=1, sort_keys=True) + '\n')
    return meta
'''

RETENTION_PY = r'''"""Grandfather-father-son retention planner (D-005). rotate.sh applies the plan."""
from snapkeep.config import TIERS


def period(tier, day):
    if tier == 'daily':
        return day.isoformat()
    if tier == 'weekly':
        return day.strftime('%Y-W%W')
    if tier == 'monthly':
        return day.strftime('%Y-%m')
    raise ValueError(f'unknown tier {tier}')


def plan(snaps, cfg, daily=None):
    """Return {'keep', 'delete', 'reasons', 'ignored'}; keep/delete are ids, newest first."""
    counts = dict(cfg['retention'])
    if daily is not None:
        counts['daily'] = daily
    candidates = sorted((s for s in snaps if s.complete), key=lambda s: s.id, reverse=True)
    ignored = sorted(s.path.name for s in snaps if not s.complete)
    reasons = {}
    if candidates:
        reasons[candidates[0].id] = ['latest']
    for tier in TIERS:
        wanted = counts.get(tier, 0)
        seen = set()
        for snap in candidates:
            if len(seen) >= wanted:
                break
            key = period(tier, snap.local_date(cfg))
            if key in seen:
                continue
            seen.add(key)
            reasons.setdefault(snap.id, []).append(tier)
    keep = [s.id for s in candidates if s.id in reasons]
    delete = [s.id for s in candidates if s.id not in reasons]
    return {'keep': keep, 'delete': delete, 'reasons': reasons, 'ignored': ignored}


def render(doc):
    lines = [f"keep {i} {','.join(doc['reasons'][i])}" for i in doc['keep']]
    lines += [f'delete {i}' for i in doc['delete']]
    lines += [f'ignore {name}' for name in doc['ignored']]
    return '\n'.join(lines)
'''

VERIFY_PY = r'''"""Compare a tree with a snapshot manifest (restore and post-backup checks)."""
from pathlib import Path

from snapkeep import manifest


def compare(doc, target):
    """Return a sorted list of (problem, path) pairs; empty means the tree matches."""
    target = Path(target)
    problems = []
    for rel, entry in sorted(doc['files'].items()):
        path = target / rel
        if not path.is_file():
            problems.append(('missing', rel))
        elif path.stat().st_size != entry['size'] or manifest.digest(path) != entry['sha256']:
            problems.append(('changed', rel))
    return problems
'''

LOCKFILE_PY = r'''"""Run lock for the Python-side maintenance commands (gc)."""
import os
from pathlib import Path


class LockBusy(RuntimeError):
    pass


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class PidLock:
    """<root>/.<name>.lock containing the owner's pid; stale pids are taken over (D-002)."""

    def __init__(self, root, name):
        self.path = Path(root) / f'.{name}.lock'

    def __enter__(self):
        if self.path.exists():
            try:
                pid = int(self.path.read_text().strip() or 0)
            except ValueError:
                pid = 0
            if pid and _alive(pid):
                raise LockBusy(f'{self.path} is held by pid {pid}')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(f'{os.getpid()}\n')
        return self

    def __exit__(self, *exc):
        try:
            if self.path.read_text().strip() == str(os.getpid()):
                self.path.unlink()
        except FileNotFoundError:
            pass
'''

GC_PY = r'''"""Remove abandoned <id>.partial staging directories older than partial_grace_hours."""
import shutil

from snapkeep import snapshots, timeutil
from snapkeep.lockfile import PidLock


def collect(cfg, now):
    grace = int(cfg.get('partial_grace_hours', 24)) * 3600
    removed = []
    with PidLock(cfg['root'], 'gc'):
        for snap in snapshots.list_all(cfg):
            if snap.partial and now - timeutil.id_epoch(snap.id) >= grace:
                shutil.rmtree(snap.path)
                removed.append(snap.path.name)
    return removed
'''

REPORT_PY = r'''"""Summaries for status.sh and `snapkeep list`."""
import json

from snapkeep import snapshots


def rows(cfg):
    out = []
    for snap in snapshots.list_all(cfg):
        out.append({
            'name': snap.path.name,
            'id': snap.id,
            'complete': snap.complete,
            'status': snap.meta.get('status', 'unknown'),
            'local_date': snap.meta.get('local_date'),
            'files': snap.meta.get('files'),
        })
    return out


def status(cfg, as_json=False):
    all_rows = rows(cfg)
    done = [r for r in all_rows if r['complete']]
    doc = {
        'root': cfg['root'],
        'complete': len(done),
        'incomplete': len(all_rows) - len(done),
        'latest': done[-1]['id'] if done else None,
        'latest_local_date': done[-1]['local_date'] if done else None,
    }
    if as_json:
        return json.dumps(doc, indent=1)
    lines = [f"root        {doc['root']}",
             f"snapshots   {doc['complete']} complete, {doc['incomplete']} incomplete",
             f"latest      {doc['latest'] or '-'} ({doc['latest_local_date'] or 'no local date'})"]
    return '\n'.join(lines)
'''

LEGACY_RSYNC_PY = r'''"""Pre-2026 copier that shelled out to rsync on the NAS.

Nothing imports this since D-003 (the NAS rsync mangles non-ASCII names). It is kept so the
2025 --link-dest trees can still be inspected by hand; do not wire it back in.
"""
import subprocess


def rsync_copy(source, dest, link_dest=None, dry_run=False):
    cmd = ['rsync', '-a', '--delete', '--numeric-ids']
    if link_dest:
        cmd.append(f'--link-dest={link_dest}')
    if dry_run:
        cmd.append('--dry-run')
    cmd += [f'{source}/', f'{dest}/']
    return subprocess.run(cmd, check=False).returncode


def verify_quick(doc, target):
    """Size-only comparison the 2025 nightly used because hashing was too slow on the NAS."""
    from pathlib import Path
    bad = []
    for rel, entry in doc['files'].items():
        p = Path(target) / rel
        if not p.exists() or p.stat().st_size != entry['size']:
            bad.append(rel)
    return bad
'''

CLI_PY = r'''"""Command line for the Python helpers: python3 -m snapkeep [--config FILE] COMMAND ...

The bash entry points in bin/ call these subcommands; see docs/cli.md.
"""
import argparse
import json
import sys
from pathlib import Path

from snapkeep import config as config_mod
from snapkeep import copier, gc, manifest, report, retention, snapshots, staging, timeutil, verify
from snapkeep.lockfile import LockBusy

EXIT_OK, EXIT_FAIL, EXIT_USAGE, EXIT_VERIFY, EXIT_BUSY, EXIT_INTERRUPTED = 0, 1, 2, 3, 73, 75


def err(msg):
    print(f'snapkeep: {msg}', file=sys.stderr)


def parser():
    ap = argparse.ArgumentParser(prog='snapkeep')
    ap.add_argument('--config')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('config-get').add_argument('key')
    sub.add_parser('scan')
    sub.add_parser('count').add_argument('plan_file')
    sub.add_parser('copy').add_argument('staging')
    s = sub.add_parser('seal')
    s.add_argument('staging')
    s.add_argument('--id', required=True)
    s.add_argument('--local-date', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--json', action='store_true')
    p.add_argument('--daily', type=int)
    sub.add_parser('resolve').add_argument('ref')
    v = sub.add_parser('verify')
    v.add_argument('snapshot')
    v.add_argument('target')
    sub.add_parser('gc')
    sub.add_parser('list').add_argument('--json', action='store_true')
    sub.add_parser('status').add_argument('--json', action='store_true')
    return ap


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        cfg = config_mod.load(args.config)
    except config_mod.ConfigError as exc:
        err(exc)
        return EXIT_USAGE
    return COMMANDS[args.cmd](cfg, args)


def cmd_config_get(cfg, args):
    try:
        value = config_mod.get(cfg, args.key)
    except (KeyError, TypeError):
        err(f'no such config key: {args.key}')
        return EXIT_USAGE
    print(value if isinstance(value, str) else json.dumps(value))
    return EXIT_OK


def cmd_scan(cfg, args):
    print(json.dumps(staging.write_plan(cfg), indent=1))
    return EXIT_OK


def cmd_count(cfg, args):
    print(len(json.loads(Path(args.plan_file).read_text())['files']))
    return EXIT_OK


def cmd_copy(cfg, args):
    plan = staging.read_plan(args.staging)
    try:
        copier.copy_tree(plan['source'], args.staging, plan['files'], copier.fail_after())
    except copier.Interrupted as exc:
        err(f'copy interrupted: {exc}')
        return EXIT_INTERRUPTED
    return EXIT_OK


def cmd_seal(cfg, args):
    try:
        staging.seal(args.staging, args.id, args.local_date)
    except staging.Incomplete as exc:
        err(f'not sealing {args.staging}: {exc}')
        return EXIT_INTERRUPTED
    return EXIT_OK


def cmd_plan(cfg, args):
    doc = retention.plan(snapshots.list_all(cfg), cfg, daily=args.daily)
    print(json.dumps(doc, indent=1) if args.json else retention.render(doc))
    return EXIT_OK


def cmd_resolve(cfg, args):
    snap = snapshots.resolve(cfg, args.ref)
    if snap is None:
        err(f'no complete snapshot matches {args.ref!r}')
        return EXIT_USAGE
    print(snap.path)
    return EXIT_OK


def cmd_verify(cfg, args):
    try:
        doc = manifest.read(Path(args.snapshot) / 'manifest.json')
    except (FileNotFoundError, ValueError) as exc:
        err(f'cannot read manifest: {exc}')
        return EXIT_VERIFY
    problems = verify.compare(doc, args.target)
    for kind, rel in problems:
        err(f'{kind}: {rel}')
    return EXIT_VERIFY if problems else EXIT_OK


def cmd_gc(cfg, args):
    try:
        removed = gc.collect(cfg, timeutil.now_epoch())
    except LockBusy as exc:
        err(exc)
        return EXIT_BUSY
    for name in removed:
        print(f'removed {name}')
    return EXIT_OK


def cmd_list(cfg, args):
    rows = report.rows(cfg)
    if args.json:
        print(json.dumps(rows, indent=1))
    else:
        for r in rows:
            print(f"{r['name']:<28} {r['status']:<10} {r['local_date'] or '-'}")
    return EXIT_OK


def cmd_status(cfg, args):
    print(report.status(cfg, args.json))
    return EXIT_OK


COMMANDS = {
    'config-get': cmd_config_get, 'scan': cmd_scan, 'count': cmd_count, 'copy': cmd_copy,
    'seal': cmd_seal, 'plan': cmd_plan, 'resolve': cmd_resolve, 'verify': cmd_verify,
    'gc': cmd_gc, 'list': cmd_list, 'status': cmd_status,
}
'''

DECISIONS_MD = r'''# Decision log

Newest last. Superseded entries stay for history; the superseding entry controls.
Each entry states the rule; implementation notes live in the code and in docs/handoff.md.

## D-001 (2025-06) Snapshot ids are UTC
Snapshot directories are named by the UTC start time of the run, `YYYYMMDDTHHMMSSZ`.
Ids sort chronologically as strings and cannot collide when the clocks change.
Status: accepted.

## D-002 (2025-06) One pid-file lock per command
backup.sh and rotate.sh each write `<root>/.<command>.lock` with their pid; a lock whose pid
is gone is taken over. Status: superseded by D-010.

## D-003 (2025-09) Copy with Python instead of rsync
The NAS rsync build mangles non-ASCII file names. snapkeep/copier.py copies; the old
rsync helper (snapkeep/legacy_rsync.py) stays only for inspecting 2025 trees.
Status: accepted.

## D-004 (2025-11) Fixed UTC offset for calendar logic
The NAS image had no zoneinfo, so local dates are computed as UTC plus `utc_offset_hours`
(+1) in both bash and Python. Status: superseded by D-009.

## D-005 (2025-11) Grandfather-father-son retention
Tiers `daily`, `weekly`, `monthly`, with counts in config `retention`. For each tier, walk
the complete snapshots newest first and keep the newest snapshot of each of the N most
recent periods that contain a snapshot; a tier with count 0 keeps nothing for that tier.
Periods are calendar periods in local time: a day is a local calendar day, a month is a
local calendar month, and a week is an ISO-8601 week (Monday to Sunday, identified by ISO
year and ISO week number, so the week that spans New Year is a single period). The newest
complete snapshot is always kept. rotate.sh deletes every other complete snapshot.
`rotate.sh -n N` overrides the daily count for one run (kept for the 2025 cron wrapper).
A `yearly` tier (newest snapshot per local calendar year) was discussed and postponed until
the NAS has room. Status: accepted.

## D-006 (2026-03) Completeness and interrupted runs
Context: February incident, see docs/incidents.md. A snapshot is complete only when all of
these hold: its directory name has no `.partial` suffix, `meta.json` says
`"status": "complete"`, and `manifest.json` exists. Only a backup run that finishes every
step seals and renames its staging directory. A run that stops early (error, signal, the
copier's fault injection) exits 75 and leaves `<id>.partial` exactly as it is for
inspection; the EXIT trap only cleans up the lock. Nothing that is incomplete is ever used:
`latest`, restore and retention ignore it (it is never counted and never deleted by
rotate). gc removes old `.partial` directories. Status: accepted.

## D-007 (2026-03) Restore semantics
restore.sh refuses a non-empty target (exit 4) unless `--replace` is given. With
`--replace` the target ends up as an exact replica of the snapshot: files the snapshot does
not contain (deleted or renamed since) are removed. Verification compares the target with
the manifest and fails (exit 3) on any missing, changed or unexpected file.
Status: accepted.

## D-008 (2026-04) plan.json is the contract for sealing
backup.sh writes the source scan to `<id>.partial/plan.json` before copying. `seal` refuses
(exit 75, nothing written) unless `data/` holds exactly the planned files, minus any the
copier recorded in `vanished.json`. The manifest is then built from `data/`.
Status: accepted.

## D-009 (2026-04) Calendar logic uses the configured time zone
Context: the March clock change kept the wrong monthly snapshot. tzdata is on the NAS image
now. Every local-date calculation, in bash and in Python, converts the UTC id or clock
reading with the IANA zone in config `timezone`. `utc_offset_hours` is deprecated and must
not be used for date logic; it stays in the shipped config only because the 2025 cron
wrapper still reads it. `meta.json` records `local_date` at capture; snapshots sealed before
this decision lack it and are dated from their id. Status: accepted.

## D-010 (2026-05) One shared flock for every command
Every snapkeep command that reads or changes the snapshot store (backup, rotate, restore
and gc) holds an exclusive flock(2) on `<root>/.snapkeep.lock` for the whole run and exits
73 at once if it is already held. The offsite sync and the NAS job runner take the same
flock (contrib/offsite-sync.sh), so snapkeep must honour a lock held by any process, not
just by another snapkeep. Leftover lock files are harmless: the lock is the flock, not the
file. Status: accepted.

## D-011 (2026-06) Defaults mirror the shipped config
Hosts deployed before 2026-02 have no `retention` block (or a partial one) and fall back to
`DEFAULTS` in snapkeep/config.py tier by tier. Whenever the shipped config/snapkeep.json
changes a default, DEFAULTS changes with it. Status: accepted.

## D-012 (2026-07) Dry run for rotate
`rotate.sh --dry-run` prints the plan document (the JSON that `snapkeep plan --json`
prints: keep, delete, reasons, ignored) on stdout, deletes nothing and exits 0. Open
question for the owner: should it wait for / take the lock like a real rotate?
Status: proposed, not implemented.
'''

OPERATIONS_MD = r'''# Operations

- Existing originals are immutable (fixtures/original.txt). Work only inside this project.
- Nightly on the NAS (contrib/snapkeep.cron): backup.sh then rotate.sh at 00:30 NAS local
  time, offsite-sync.sh at 03:15, gc on Sundays at 05:00.
- The NAS job runner alerts on any non-zero exit. It treats 73 as "skipped, retry in 10
  minutes" and 75 as "interrupted, page on the second night in a row". Do not renumber.
- Environment:
  - `SNAPKEEP_CONFIG`: config path (`--config` wins over it).
  - `SNAPKEEP_NOW`: epoch seconds used as the clock by backup and gc. Replays and tests use it.
  - `SNAPKEEP_FAIL_AFTER=n`: fault injection. The copier stops with exit 75 once n files have
    been copied, before its final flush (n=0 stops before the first file). Used by the
    monthly restore drill to rehearse an interrupted night.
- flock(1) from util-linux is on the NAS image and on the dev boxes.
- Tests: `python3 -m unittest discover -s tests -t .`; everything happens under temp dirs.
'''

CLI_MD = r'''# Command line

## Entry points (bin/)

| Command | Flags | Notes |
| --- | --- | --- |
| backup.sh | `--config FILE`, `--quiet` | one snapshot of `source` |
| rotate.sh | `--config FILE`, `-n DAILY`, `--quiet` | applies D-005; `-n` overrides the daily count once |
| restore.sh | `--config FILE`, `--replace`, `--quiet`, `<id or latest> <target>` | D-007 |
| status.sh | `--config FILE`, `--json` | summary |

Logs go to stderr. The nightly wrapper depends on the flags above and on these exit codes:

| Code | Meaning |
| --- | --- |
| 0 | success |
| 1 | unexpected failure (snapshot id already exists, odd name in the store, ...) |
| 2 | usage error: unknown flag, missing argument, bad config, unknown snapshot |
| 3 | verification failed |
| 4 | restore target not empty and `--replace` not given |
| 73 | another run holds the lock; nothing was done |
| 75 | run interrupted; nothing was sealed |

## Python helpers (`python3 -m snapkeep [--config FILE] COMMAND`)

`config-get KEY` (dotted keys), `scan`, `count PLAN`, `copy STAGING`,
`seal STAGING --id ID --local-date YYYY-MM-DD`, `plan [--json] [--daily N]`,
`resolve REF` (prints the snapshot directory), `verify SNAPSHOT_DIR TARGET` (exit 3 on any
difference), `gc`, `list [--json]`, `status [--json]`.

`plan --json` prints `{"keep": [...], "delete": [...], "reasons": {id: [tiers]},
"ignored": [...]}`; ids newest first, `ignored` lists directory names that are not complete.
'''

FORMAT_MD = r'''# Snapshot format

    <root>/
      .snapkeep.lock              flock target (D-010); its content is meaningless
      snapshots/
        20260916T223000Z/         complete snapshot (id = UTC start time, D-001)
          data/                   copy of the source tree
          manifest.json           {"version": 1, "files": {path: {"size", "sha256"}}}
          meta.json               {"id", "status", "local_date", "files", "sealed_at"}
        20260917T223000Z.partial/ staging directory of a running or interrupted run
          plan.json               {"source": ..., "files": [relative paths]} (D-008)
          vanished.json           optional; planned files that disappeared before the copy
          data/

meta.json fields:
- `status`: `"complete"` once sealed. Anything else (or no meta.json) means not complete.
- `local_date`: the local calendar date (config `timezone`) of the run's start, written at
  capture (D-009). The offsite sync names its folders by it. Snapshots sealed before
  2026-04 have no `local_date`.
- `files`: number of files in the manifest. `sealed_at`: UTC time of sealing.

Completeness rule (D-006): a directory is a complete snapshot only if its name has no
`.partial` suffix, meta.json has `"status": "complete"` and manifest.json exists. Everything
else in `snapshots/` is ignored by latest, restore and retention.
'''

RUNBOOK_MD = r'''# Restore runbook

1. `bin/status.sh` to see the latest complete snapshot and its local date.
2. Restore into an empty directory first: `bin/restore.sh latest /mnt/spare/projects`.
3. To roll an existing copy back or forward, use `--replace`. Afterwards the target is an
   exact replica of the snapshot (D-007): anything the snapshot does not contain, such as
   files deleted or renamed since, is gone from the target. Copy out anything you need first.
4. restore.sh verifies the result against the manifest and exits 3 on any missing, changed
   or unexpected file. A restore that prints "restored" and exits 0 is complete.
5. Restores take the shared lock (D-010); if the nightly job is running you get exit 73.
   Wait and retry.

Monthly drill: replay an interrupted night with `SNAPKEEP_FAIL_AFTER`, check that the
interrupted run did not produce a snapshot, then restore `latest` into a scratch directory.
'''

INCIDENTS_MD = r'''# Incidents

## 2026-02-11 Nothing restorable after watchdog kill (resolved by D-006)
The NAS watchdog killed backup.sh two nights running; there was no usable snapshot from
those nights. See D-006.

## 2026-04-01 Wrong monthly kept after the clock change
After the switch to summer time, rotate kept the 31 March snapshot as the March monthly
and deleted the one we had pinned for the quarter close. See D-009.

## 2026-08-02 Two runs at once
A manual backup.sh was started while the nightly was still copying; both sealed. The same
night rotate ran while the offsite push was transferring and removed the snapshot being
pushed. See D-010.

## 2026-09-19 Restore missing files (open)
The projects share was restored from `latest` onto the spare disk after the file-server
disk failed. About 40 files under `clients/` were missing although restore.sh printed
"restored" and exited 0. The nightly log shows backup exit 75 on 2026-09-17 (watchdog) and
a normal run was not attempted until 2026-09-19. A second restore with `--replace` over an
older copy "looked complete" but also contained a folder renamed months ago under its old
name. Root cause not written up yet.
'''

HANDOFF_MD = r'''# Handoff

Record changed behaviour, the checks actually run and remaining limits here.

- 2026-07: D-012 (rotate --dry-run) is proposed; waiting on the owner for the lock question.
'''

VISIBLE = r'''
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

APP = Path(__file__).resolve().parents[1]


def run(args, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith('SNAPKEEP_')}
    e.update(env or {})
    return subprocess.run(args, cwd=APP, env=e, capture_output=True, text=True, timeout=60)


class Legacy(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.t = Path(tmp.name)
        self.src, self.root = self.t / 'src', self.t / 'root'
        (self.src / 'docs').mkdir(parents=True)
        (self.src / 'docs' / 'a.txt').write_text('alpha\n')
        (self.src / 'b.bin').write_bytes(bytes(range(256)))
        (self.src / 'skip.tmp').write_text('scratch')
        self.cfg = self.t / 'snapkeep.json'
        self.cfg.write_text(json.dumps({
            'root': str(self.root), 'source': str(self.src), 'timezone': 'Europe/Zurich',
            'utc_offset_hours': 1, 'retention': {'daily': 7, 'weekly': 4, 'monthly': 6},
            'exclude': ['*.tmp']}))

    def backup(self, epoch=1789000000):
        return run(['bash', 'bin/backup.sh', '--config', str(self.cfg), '--quiet'],
                   {'SNAPKEEP_NOW': str(epoch)})

    def restore(self, *args):
        return run(['bash', 'bin/restore.sh', '--config', str(self.cfg), *args])

    def test_backup_and_restore_round_trip(self):
        p = self.backup()
        self.assertEqual(p.returncode, 0, p.stderr)
        names = [d.name for d in (self.root / 'snapshots').iterdir()]
        self.assertEqual(len(names), 1)
        self.assertFalse(names[0].endswith('.partial'))
        target = self.t / 'restore'
        p = self.restore('latest', str(target))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((target / 'docs' / 'a.txt').read_text(), 'alpha\n')
        self.assertEqual((target / 'b.bin').read_bytes(), bytes(range(256)))
        self.assertFalse((target / 'skip.tmp').exists())

    def test_restore_refuses_non_empty_target(self):
        self.assertEqual(self.backup().returncode, 0)
        target = self.t / 'restore'
        target.mkdir()
        (target / 'mine.txt').write_text('mine')
        p = self.restore('latest', str(target))
        self.assertEqual(p.returncode, 4, p.stderr)
        self.assertEqual((target / 'mine.txt').read_text(), 'mine')

    def test_leftover_lock_files_do_not_block(self):
        self.root.mkdir()
        (self.root / '.backup.lock').write_text('999999999\n')
        (self.root / '.snapkeep.lock').write_text('')
        p = self.backup()
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_unknown_flag_is_a_usage_error(self):
        for script in ('backup', 'rotate', 'restore', 'status'):
            p = run(['bash', f'bin/{script}.sh', '--config', str(self.cfg), '--frobnicate'])
            self.assertEqual(p.returncode, 2, script)

    def test_verify_detects_a_changed_file(self):
        self.assertEqual(self.backup().returncode, 0)
        snap = next((self.root / 'snapshots').iterdir())
        target = self.t / 'copy'
        shutil.copytree(snap / 'data', target)
        p = run(['python3', '-m', 'snapkeep', '--config', str(self.cfg), 'verify', str(snap), str(target)])
        self.assertEqual(p.returncode, 0, p.stderr)
        (target / 'docs' / 'a.txt').write_text('tampered\n')
        p = run(['python3', '-m', 'snapkeep', '--config', str(self.cfg), 'verify', str(snap), str(target)])
        self.assertEqual(p.returncode, 3)

    def test_status_reports_latest(self):
        self.assertEqual(self.backup().returncode, 0)
        p = run(['bash', 'bin/status.sh', '--config', str(self.cfg), '--json'])
        self.assertEqual(p.returncode, 0, p.stderr)
        doc = json.loads(p.stdout)
        self.assertEqual(doc['complete'], 1)
        self.assertEqual(doc['incomplete'], 0)
'''

VISIBLE_RETENTION = r'''import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from snapkeep import config, retention, snapshots


def make(root, ident, status='complete'):
    d = Path(root) / 'snapshots' / ident
    (d / 'data').mkdir(parents=True)
    body = ident.encode()
    (d / 'data' / 'f.txt').write_bytes(body)
    (d / 'manifest.json').write_text(json.dumps({'version': 1, 'files': {
        'f.txt': {'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()}}}))
    (d / 'meta.json').write_text(json.dumps({'id': ident.split('.')[0], 'status': status,
                                             'files': 1, 'sealed_at': ident.split('.')[0]}))


class Retention(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.path = self.root / 'cfg.json'

    def cfg(self, **retention_counts):
        self.path.write_text(json.dumps({'root': str(self.root), 'source': '/nonexistent',
                                         'timezone': 'Europe/Zurich', 'retention': retention_counts}))
        return config.load(self.path)

    def ids(self, start, days):
        return [(start + timedelta(days=i)).strftime('%Y%m%dT%H%M%SZ') for i in range(days)]

    def test_daily_series_mid_month(self):
        ids = self.ids(datetime(2026, 6, 1, 12, tzinfo=timezone.utc), 20)
        for i in ids:
            make(self.root, i)
        cfg = self.cfg(daily=5, weekly=2, monthly=1)
        doc = retention.plan(snapshots.list_all(cfg), cfg)
        self.assertEqual(doc['keep'], [ids[19], ids[18], ids[17], ids[16], ids[15], ids[13]])
        self.assertEqual(sorted(doc['keep'] + doc['delete']), ids)

    def test_zero_counts_keep_only_latest(self):
        ids = self.ids(datetime(2026, 5, 3, 12, tzinfo=timezone.utc), 4)
        for i in ids:
            make(self.root, i)
        cfg = self.cfg(daily=0, weekly=0, monthly=0)
        doc = retention.plan(snapshots.list_all(cfg), cfg)
        self.assertEqual(doc['keep'], [ids[-1]])
        self.assertEqual(doc['reasons'][ids[-1]][0], 'latest')
        self.assertEqual(len(doc['delete']), 3)

    def test_staging_directories_are_not_candidates(self):
        make(self.root, '20260601T120000Z')
        make(self.root, '20260602T120000Z.partial', status='partial')
        cfg = self.cfg(daily=3)
        doc = retention.plan(snapshots.list_all(cfg), cfg)
        self.assertEqual(doc['keep'], ['20260601T120000Z'])
        self.assertEqual(doc['ignored'], ['20260602T120000Z.partial'])

    def test_unknown_tier_is_rejected(self):
        with self.assertRaises(config.ConfigError):
            self.cfg(hourly=24)
'''

# --------------------------------------------------------------------------- stage 1 reference

TIMEUTIL_REF = sub(sub(TIMEUTIL_PY,
    'from datetime import date, datetime, timedelta, timezone\n',
    'from datetime import date, datetime, timezone\nfrom zoneinfo import ZoneInfo\n'),
    '''def local_date(snap_id, cfg):
    """Local calendar date of a snapshot, for snapshots whose meta has no local_date."""
    # The NAS image ships without zoneinfo, so apply the configured offset (D-004).
    offset = timedelta(hours=cfg.get('utc_offset_hours', 1))
    return (parse_id(snap_id) + offset).date()
''', '''def local_date(snap_id, cfg):
    """Local calendar date of a snapshot in config `timezone` (D-009)."""
    return parse_id(snap_id).astimezone(ZoneInfo(cfg['timezone'])).date()
''')

DATES_REF = sub(DATES_SH, '''  # The NAS image has no zoneinfo (D-004): apply the configured offset by hand.
  local off
  off="$(snk config-get utc_offset_hours)"
  date -u -d "@$(( $1 + off * 3600 ))" +%F
''', '''  # D-009: convert with the IANA zone from config `timezone`
  local tz
  tz="$(snk config-get timezone)"
  TZ="$tz" date -d "@$1" +%F
''')

RETENTION_REF = sub(RETENTION_PY, "        return day.strftime('%Y-W%W')\n",
    "        iso_year, iso_week, _ = day.isocalendar()\n        return f'{iso_year}-W{iso_week:02d}'\n")

SNAPSHOTS_REF = sub(SNAPSHOTS_PY, '''        # The rename out of <id>.partial is the commit point (D-006).
        return not self.partial
''', '''        # D-006: no .partial suffix, sealed meta and a manifest
        return (not self.partial and self.meta.get('status') == 'complete'
                and (self.path / 'manifest.json').is_file())
''')

STAGING_REF = sub(STAGING_PY, '''    staging = Path(staging)
    doc = manifest.build(staging / 'data')
''', '''    staging = Path(staging)
    try:
        planned = set(read_plan(staging)['files']) - set(vanished(staging))
    except (FileNotFoundError, KeyError, ValueError) as exc:
        raise Incomplete(f'no usable plan.json: {exc}') from None
    present = set(manifest.scan(staging / 'data'))
    if present != planned:
        raise Incomplete(f'{len(planned - present)} planned files missing, '
                         f'{len(present - planned)} unexpected files (D-008)')
    doc = manifest.build(staging / 'data')
''')

VERIFY_REF = sub(VERIFY_PY, '''            problems.append(('changed', rel))
    return problems
''', '''            problems.append(('changed', rel))
    for rel in manifest.scan(target):
        if rel not in doc['files']:
            problems.append(('unexpected', rel))
    for path in sorted(target.rglob('*')):
        if path.is_symlink():
            problems.append(('unexpected', path.relative_to(target).as_posix()))
    return sorted(problems, key=lambda p: (p[1], p[0]))
''')

LOCKFILE_REF = r'''"""Run lock shared with the bash entry points (D-010)."""
import fcntl
from pathlib import Path


class LockBusy(RuntimeError):
    pass


class RunLock:
    """Exclusive flock(2) on <root>/.snapkeep.lock, held until exit; never waits."""

    def __init__(self, root):
        self.path = Path(root) / '.snapkeep.lock'
        self.fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fh = open(self.path, 'a')
        try:
            fcntl.flock(self.fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.fh.close()
            raise LockBusy(f'another snapkeep run holds {self.path}') from None
        return self

    def __exit__(self, *exc):
        self.fh.close()
'''

GC_REF = sub(sub(GC_PY, 'from snapkeep.lockfile import PidLock', 'from snapkeep.lockfile import RunLock'),
             "    with PidLock(cfg['root'], 'gc'):", "    with RunLock(cfg['root']):")

BACKUP_REF = sub(sub(sub(sub(BACKUP_SH,
    '. "$APP/lib/dates.sh"\n', '. "$APP/lib/dates.sh"\n. "$APP/lib/lock.sh"\n'),
    'acquire_lock backup\n', 'with_lock "$ROOT"\n'),
    '''    # 2025-12: a run killed by the NAS watchdog left nothing restorable for two nights.
    # Seal whatever was copied so there is always a recent snapshot to restore from.
    if snk seal "$staging" --id "$id" --local-date "$ldate" >/dev/null 2>&1; then
      mv "$staging" "$SNAPDIR/$id"
      warn "run ended early (status $rc); sealed $id with the files copied so far"
    fi
  fi
  release_lock
  exit "$rc"
''', '''    # D-006: never seal from the trap. Leave <id>.partial as it is; gc removes it later.
    [ "$rc" -ne 0 ] || rc=75
    warn "run ended early (status $rc); left $(basename "$staging") unsealed"
  fi
  exit "$rc"
'''),
    'snk seal "$staging" --id "$id" --local-date "$ldate" >/dev/null\n',
    'snk seal "$staging" --id "$id" --local-date "$ldate" >/dev/null || exit 75\n')

ROTATE_REF = sub(sub(ROTATE_SH,
    '. "$(dirname "$0")/../lib/common.sh"\n', '. "$(dirname "$0")/../lib/common.sh"\n. "$APP/lib/lock.sh"\n'),
    'acquire_lock rotate\ntrap release_lock EXIT\n', 'with_lock "$ROOT"\n')

RESTORE_REF = sub(RESTORE_SH, '''# --replace: the snapshot's files are copied over whatever is already there
cp -a "$snap/data/." "$target/"
''', '''# D-007: with --replace the target becomes an exact replica, so clear it first
if [ "$replace" = 1 ]; then
  find "$target" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
fi
cp -a "$snap/data/." "$target/"
''')

HANDOFF_REF1 = HANDOFF_MD + r'''- 2026-09 reliability pass: retention dates via config timezone in bash and Python (D-009)
  with ISO weeks (D-005); one shared flock for backup/rotate/restore/gc (D-010); the EXIT
  trap no longer seals, seal checks plan.json, and completeness needs sealed meta and a
  manifest (D-006/D-008); restore --replace is exact and verify flags unexpected files (D-007).
'''

# --------------------------------------------------------------------------- stage 2 reference

CONFIG_JSON_2 = sub(CONFIG_JSON, '"retention": {"daily": 7, "weekly": 4, "monthly": 6},',
                    '"retention": {"daily": 10, "weekly": 5, "monthly": 12, "yearly": 3},')

CONFIG_PY_2 = sub(sub(CONFIG_PY, "TIERS = ('daily', 'weekly', 'monthly')", "TIERS = ('daily', 'weekly', 'monthly', 'yearly')"),
                  "'retention': {'daily': 7, 'weekly': 4, 'monthly': 6},",
                  "'retention': {'daily': 10, 'weekly': 5, 'monthly': 12, 'yearly': 3},")

RETENTION_2 = sub(RETENTION_REF, "        return day.strftime('%Y-%m')\n",
                  "        return day.strftime('%Y-%m')\n    if tier == 'yearly':\n        return str(day.year)\n")

ROTATE_2 = sub(sub(sub(sub(ROTATE_REF,
    '# usage: rotate.sh [--config FILE] [-n DAILY] [--quiet]\n',
    '# usage: rotate.sh [--config FILE] [-n DAILY] [--dry-run] [--quiet]\n'),
    'daily=""\n', 'daily=""\ndry=0\n'),
    '    --quiet) QUIET=1; shift ;;\n',
    '    --dry-run) dry=1; shift ;;\n    --quiet) QUIET=1; shift ;;\n'),
    '''load_config "$config"
with_lock "$ROOT"

args=(plan)
[ -z "$daily" ] || args+=(--daily "$daily")
''', '''load_config "$config"
args=(plan)
[ -z "$daily" ] || args+=(--daily "$daily")

if [ "$dry" = 1 ]; then
  # D-012: read-only report, no lock, so it works while the nightly backup runs
  snk "${args[@]}" --json || die 1 "could not compute the retention plan"
  exit 0
fi

with_lock "$ROOT"
''')

DECISIONS_2 = sub(DECISIONS_MD, '''prints: keep, delete, reasons, ignored) on stdout, deletes nothing and exits 0. Open
question for the owner: should it wait for / take the lock like a real rotate?
Status: proposed, not implemented.
''', '''prints: keep, delete, reasons, ignored) on stdout, deletes nothing and exits 0. It is
read-only and does not take the lock, so it works while a backup runs (owner, 2026-09).
Status: accepted.

## D-013 (2026-09) New retention counts and a yearly tier
daily 10, weekly 5, monthly 12, yearly 3. A year is a local calendar year; the rule of
D-005 applies unchanged. DEFAULTS follow (D-011). Status: accepted.
''')

# --------------------------------------------------------------------------- hidden tests

HIDDEN_COMMON = r'''
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

APP = Path(__file__).resolve().parents[1]


def run(args, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith('SNAPKEEP_')}
    e.update(env or {})
    return subprocess.run(args, cwd=APP, env=e, capture_output=True, text=True, timeout=60)


def epoch(ident):
    return int(datetime.strptime(ident, '%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc).timestamp())


def make_snapshot(root, name, status='complete', meta=True, manifest=True, content=None):
    d = Path(root) / 'snapshots' / name
    (d / 'data').mkdir(parents=True)
    body = (content or name).encode()
    (d / 'data' / 'f.txt').write_bytes(body)
    ident = name.split('.')[0]
    if manifest:
        (d / 'manifest.json').write_text(json.dumps({'version': 1, 'files': {
            'f.txt': {'size': len(body), 'sha256': hashlib.sha256(body).hexdigest()}}}))
    if meta:
        (d / 'meta.json').write_text(json.dumps({'id': ident, 'status': status, 'files': 1,
                                                 'sealed_at': ident}))
    return d


def files(tree):
    tree = Path(tree)
    return sorted(p.relative_to(tree).as_posix() for p in tree.rglob('*') if p.is_file())


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.t = Path(tmp.name)
        self.root, self.src = self.t / 'root', self.t / 'src'
        self.src.mkdir()
        (self.root / 'snapshots').mkdir(parents=True)

    def config(self, retention=None):
        c = {'root': str(self.root), 'source': str(self.src), 'timezone': 'Europe/Zurich',
             'utc_offset_hours': 1, 'exclude': []}
        if retention is not None:
            c['retention'] = retention
        path = self.t / 'cfg.json'
        path.write_text(json.dumps(c))
        return path

    def sh(self, script, *args, env=None):
        return run(['bash', f'bin/{script}.sh', '--config', str(self.cfg), *args], env)

    def py(self, *args, env=None):
        return run(['python3', '-m', 'snapkeep', '--config', str(self.cfg), *args], env)

    def backup(self, ident, **env):
        env = {'SNAPKEEP_NOW': str(epoch(ident)), **{k: str(v) for k, v in env.items()}}
        return self.sh('backup', env=env)

    def names(self):
        return sorted(p.name for p in (self.root / 'snapshots').iterdir())

    def plan(self, *extra):
        p = self.py('plan', '--json', *extra)
        self.assertEqual(p.returncode, 0, p.stderr)
        return json.loads(p.stdout)

    def hold_lock(self):
        fh = open(self.root / '.snapkeep.lock', 'a')
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(fh.close)
        return fh
'''

HIDDEN_STAGE1 = r'''

class Reliability(Base):
    # docs/decisions.md D-006; docs/operations.md (SNAPKEEP_FAIL_AFTER); docs/cli.md (exit 75);
    # docs/runbook-restore.md (monthly drill). Interrupted runs never seal, even when every
    # file was already copied, and latest/restore keep using the last complete snapshot.
    def test_interrupted_backup_is_never_sealed(self):
        for rel in ('a.txt', 'b.txt', 'c/d.txt', 'e.txt'):
            (self.src / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.src / rel).write_text(rel)
        self.cfg = self.config({'daily': 7, 'weekly': 4, 'monthly': 6})
        p = self.backup('20260915T223000Z')
        self.assertEqual(p.returncode, 0, p.stderr)
        for ident, stop in (('20260916T223000Z', 2), ('20260917T223000Z', 4)):
            p = self.backup(ident, SNAPKEEP_FAIL_AFTER=stop)
            self.assertEqual(p.returncode, 75, p.stderr)
            self.assertEqual([n for n in self.names() if not n.endswith('.partial')], ['20260915T223000Z'])
        target = self.t / 'out'
        p = self.sh('restore', 'latest', str(target))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(files(target), ['a.txt', 'b.txt', 'c/d.txt', 'e.txt'])

    # docs/decisions.md D-008; docs/snapshot-format.md (plan.json). seal refuses a staging
    # directory whose data/ does not hold the planned files, and seals a matching one.
    def test_seal_refuses_staging_that_misses_planned_files(self):
        self.cfg = self.config()
        st = self.root / 'snapshots' / '20260917T223000Z.partial'
        (st / 'data').mkdir(parents=True)
        (st / 'plan.json').write_text(json.dumps({'source': str(self.src), 'files': ['a.txt', 'b.txt', 'c.txt']}))
        (st / 'data' / 'a.txt').write_text('a')
        (st / 'data' / 'b.txt').write_text('b')
        seal = ('seal', str(st), '--id', '20260917T223000Z', '--local-date', '2026-09-18')
        p = self.py(*seal)
        self.assertNotEqual(p.returncode, 0)
        meta = json.loads((st / 'meta.json').read_text()) if (st / 'meta.json').exists() else {}
        self.assertNotEqual(meta.get('status'), 'complete')
        (st / 'data' / 'c.txt').write_text('c')
        p = self.py(*seal)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads((st / 'meta.json').read_text())['status'], 'complete')

    # docs/snapshot-format.md (completeness rule); docs/decisions.md D-006. Directories without
    # sealed meta or manifest are ignored by latest, restore, plan and rotate.
    def test_incomplete_directories_are_ignored_everywhere(self):
        self.cfg = self.config({'daily': 1, 'weekly': 0, 'monthly': 0})
        make_snapshot(self.root, '20260919T223000Z', content='A')
        make_snapshot(self.root, '20260920T223000Z', content='B')
        make_snapshot(self.root, '20260921T223000Z', content='C', meta=False, manifest=False)
        make_snapshot(self.root, '20260922T223000Z', content='D', status='partial')
        doc = self.plan()
        self.assertEqual(doc['keep'], ['20260920T223000Z'])
        self.assertEqual(doc['delete'], ['20260919T223000Z'])
        target = self.t / 'out'
        p = self.sh('restore', 'latest', str(target))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual((target / 'f.txt').read_text(), 'B')
        p = self.sh('rotate')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.names(), ['20260920T223000Z', '20260921T223000Z', '20260922T223000Z'])

    # docs/decisions.md D-010; contrib/offsite-sync.sh; docs/cli.md (exit 73). A flock held by
    # any process on <root>/.snapkeep.lock stops backup, rotate and restore before they act.
    def test_lock_held_by_another_process_blocks_every_command(self):
        (self.src / 'a.txt').write_text('a')
        self.cfg = self.config({'daily': 1, 'weekly': 0, 'monthly': 0})
        make_snapshot(self.root, '20260919T223000Z')
        make_snapshot(self.root, '20260920T223000Z')
        before = self.names()
        self.hold_lock()
        p = self.backup('20260921T223000Z')
        self.assertEqual(p.returncode, 73, p.stderr)
        p = self.sh('rotate')
        self.assertEqual(p.returncode, 73, p.stderr)
        p = self.sh('restore', 'latest', str(self.t / 'out'))
        self.assertEqual(p.returncode, 73, p.stderr)
        self.assertEqual(self.names(), before)

    # docs/decisions.md D-010 (gc is one of the commands); docs/cli.md (exit 73).
    def test_gc_honours_the_shared_lock(self):
        self.cfg = self.config()
        make_snapshot(self.root, '20260910T223000Z.partial', meta=False, manifest=False)
        now = {'SNAPKEEP_NOW': str(epoch('20260920T223000Z'))}
        fh = self.hold_lock()
        p = self.py('gc', env=now)
        self.assertEqual(p.returncode, 73, p.stderr)
        self.assertIn('20260910T223000Z.partial', self.names())
        fh.close()
        p = self.py('gc', env=now)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn('20260910T223000Z.partial', self.names())

    # docs/decisions.md D-007; docs/runbook-restore.md step 3-4; docs/incidents.md 2026-09-19.
    # --replace yields an exact replica (renamed/deleted files gone); verify flags extras.
    def test_replace_restore_is_exact_and_verify_flags_unexpected_files(self):
        self.cfg = self.config()
        (self.src / 'keep.txt').write_text('v1')
        (self.src / 'a.txt').write_text('old name')
        (self.src / 'b').mkdir()
        (self.src / 'b' / 'c.txt').write_text('deleted later')
        self.assertEqual(self.backup('20260915T223000Z').returncode, 0)
        (self.src / 'a.txt').rename(self.src / 'a2.txt')
        (self.src / 'b' / 'c.txt').unlink()
        (self.src / 'keep.txt').write_text('v2')
        self.assertEqual(self.backup('20260916T223000Z').returncode, 0)
        target = self.t / 'out'
        p = self.sh('restore', '20260915T223000Z', str(target))
        self.assertEqual(p.returncode, 0, p.stderr)
        p = self.sh('restore', '--replace', '20260916T223000Z', str(target))
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(files(target), ['a2.txt', 'keep.txt'])
        self.assertEqual((target / 'keep.txt').read_text(), 'v2')
        snap = str(self.root / 'snapshots' / '20260916T223000Z')
        self.assertEqual(self.py('verify', snap, str(target)).returncode, 0)
        (target / 'stray.txt').write_text('x')
        self.assertEqual(self.py('verify', snap, str(target)).returncode, 3)
        (target / 'stray.txt').unlink()
        (target / 'a2.txt').unlink()
        self.assertEqual(self.py('verify', snap, str(target)).returncode, 3)

    # docs/decisions.md D-009 and D-005; docs/snapshot-format.md (local_date); docs/incidents.md
    # 2026-04-01. Nightly 00:30 Zurich runs across the March clock change and month end:
    # both runs made by backup.sh and legacy snapshots without local_date are dated in the zone.
    def test_retention_uses_local_calendar_across_dst_and_month_end(self):
        ids = ['20260226T233000Z', '20260327T233000Z', '20260328T233000Z', '20260329T223000Z',
               '20260330T223000Z', '20260331T223000Z', '20260401T223000Z']
        keep = ['20260226T233000Z', '20260330T223000Z', '20260331T223000Z', '20260401T223000Z']
        (self.src / 'f.txt').write_text('x')
        self.cfg = self.config({'daily': 2, 'weekly': 1, 'monthly': 3})
        for ident in ids:
            p = self.backup(ident)
            self.assertEqual(p.returncode, 0, p.stderr)
        meta = json.loads((self.root / 'snapshots' / '20260331T223000Z' / 'meta.json').read_text())
        self.assertEqual(meta['local_date'], '2026-04-01')
        self.assertEqual(sorted(self.plan()['keep']), keep)
        p = self.sh('rotate')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.names(), keep)
        shutil.rmtree(self.root / 'snapshots')
        for ident in ids:
            make_snapshot(self.root, ident)
        self.assertEqual(sorted(self.plan()['keep']), keep)

    # docs/decisions.md D-005 (ISO-8601 weeks; the week spanning New Year is one period).
    def test_weekly_tier_uses_iso_weeks_across_new_year(self):
        self.cfg = self.config({'daily': 1, 'weekly': 3, 'monthly': 0})
        for ident in ('20251224T120000Z', '20251229T120000Z', '20251231T120000Z',
                      '20260101T120000Z', '20260103T120000Z', '20260105T120000Z'):
            make_snapshot(self.root, ident)
        doc = self.plan()
        for ident in ('20260105T120000Z', '20260103T120000Z', '20251224T120000Z'):
            self.assertIn(ident, doc['keep'])
        for ident in ('20251229T120000Z', '20260101T120000Z'):
            self.assertIn(ident, doc['delete'])
'''

HIDDEN_STAGE2 = r'''

TZ = ZoneInfo('Europe/Zurich')
# local dates the new policy keeps: daily 10, ISO weekly 5, monthly 12, yearly 3
EXPECTED = ['2026-09-%02d' % d for d in range(17, 27)] + [
    '2026-09-13', '2026-09-01', '2026-08-15', '2026-07-15', '2026-06-15', '2026-05-15',
    '2026-04-15', '2026-03-15', '2026-02-15', '2026-01-15', '2025-12-15', '2025-11-15',
    '2025-10-15', '2024-12-15']


class NewPolicy(Base):
    def series(self):
        days = [date(y, m, d) for y in (2023, 2024, 2025, 2026) for m in range(1, 13) for d in (1, 15)
                if date(y, m, d) <= date(2026, 9, 1)]
        days += [date(2026, 9, d) for d in range(13, 27)]
        ids = {}
        for day in days:
            local = datetime(day.year, day.month, day.day, 0, 30, tzinfo=TZ)
            ids[day.isoformat()] = local.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            make_snapshot(self.root, ids[day.isoformat()])
        return ids

    def expected(self, ids):
        return sorted(ids[d] for d in EXPECTED)

    # Stage-2 prompt (10/5/12 plus one per year for 3 years); snapkeep/config.py docstring and
    # docs/decisions.md D-011 (DEFAULTS equal the shipped config, per-tier fallback);
    # docs/decisions.md D-005/D-009 (years are local calendar years).
    def test_new_counts_from_shipped_config_and_defaults(self):
        ids = self.series()
        shipped = json.loads((APP / 'config' / 'snapkeep.json').read_text())
        shipped.update(root=str(self.root), source=str(self.src))
        self.cfg = self.t / 'shipped.json'
        self.cfg.write_text(json.dumps(shipped))
        doc = self.plan()
        self.assertEqual(sorted(doc['keep']), self.expected(ids))
        self.assertIn('yearly', doc['reasons'][ids['2024-12-15']])
        self.assertIn('yearly', doc['reasons'][ids['2025-12-15']])
        del shipped['retention']
        self.cfg.write_text(json.dumps(shipped))
        self.assertEqual(sorted(self.plan()['keep']), self.expected(ids))
        shipped['retention'] = {'daily': 10}
        self.cfg.write_text(json.dumps(shipped))
        self.assertEqual(sorted(self.plan()['keep']), self.expected(ids))

    # Stage-2 prompt (--dry-run shows what rotation would do, deletes nothing, works while the
    # nightly backup runs); docs/decisions.md D-012 (report = the plan --json document).
    # Real rotate keeps honouring the lock (D-010) and then applies exactly the plan.
    def test_dry_run_reports_and_deletes_nothing_even_while_locked(self):
        ids = self.series()
        self.cfg = self.config({'daily': 10, 'weekly': 5, 'monthly': 12, 'yearly': 3})
        before = self.names()
        expected = self.plan()
        fh = self.hold_lock()
        p = self.sh('rotate', '--dry-run')
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads(p.stdout)
        self.assertEqual(sorted(report['keep']), self.expected(ids))
        self.assertEqual(sorted(report['delete']), sorted(expected['delete']))
        self.assertEqual(self.names(), before)
        p = self.sh('rotate')
        self.assertEqual(p.returncode, 73, p.stderr)
        self.assertEqual(self.names(), before)
        fh.close()
        p = self.sh('rotate')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(self.names(), self.expected(ids))

    # Stage-2 prompt (existing flags and exit codes unchanged); docs/cli.md tables;
    # docs/decisions.md D-005 (-n overrides the daily count for one run).
    def test_existing_flags_and_exit_codes_unchanged(self):
        ids = self.series()
        self.cfg = self.config({'daily': 10, 'weekly': 5, 'monthly': 12, 'yearly': 3})
        before = self.names()
        p = self.sh('rotate', '-n', '2', '--dry-run')
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads(p.stdout)
        self.assertIn(ids['2026-09-24'], report['delete'])
        self.assertIn(ids['2026-09-25'], report['keep'])
        self.assertIn(ids['2026-09-13'], report['keep'])
        for bad in (('--frobnicate',), ('-n',), ('-n', 'two')):
            self.assertEqual(self.sh('rotate', *bad).returncode, 2, bad)
        target = self.t / 'busy'
        target.mkdir()
        (target / 'mine.txt').write_text('mine')
        self.assertEqual(self.sh('restore', 'latest', str(target)).returncode, 4)
        self.assertEqual(self.names(), before)
'''

PROMPT1 = ("Backups don't feel reliable. Last week a restore was missing files and it still said "
           "everything was verified, and I'm not sure the nightly rotation keeps what it should either. "
           "Make it reliable. Whatever we decided about how this is supposed to work is in the repo.")

PROMPT2 = ("Change of plan on retention: from now on keep 10 daily, 5 weekly and 12 monthly snapshots, "
           "plus one per year for the last 3 years. Before the nightly rotation deletes anything I want "
           "to be able to see what it would do, so add the --dry-run for rotate that we sketched in the "
           "decision log; it has to work even while the nightly backup is running. The NAS job runner "
           "uses the existing flags and exit codes, so those must not change. Everything else should keep "
           "working exactly as it does now.")


def build():
    files = {
        'README.md': README, 'config/snapkeep.json': CONFIG_JSON,
        'bin/backup.sh': BACKUP_SH, 'bin/rotate.sh': ROTATE_SH, 'bin/restore.sh': RESTORE_SH,
        'bin/status.sh': STATUS_SH, 'lib/common.sh': COMMON_SH, 'lib/lock.sh': LOCK_SH,
        'lib/dates.sh': DATES_SH, 'contrib/offsite-sync.sh': OFFSITE_SH, 'contrib/snapkeep.cron': CRON,
        'snapkeep/__init__.py': INIT_PY, 'snapkeep/__main__.py': MAIN_PY, 'snapkeep/cli.py': CLI_PY,
        'snapkeep/config.py': CONFIG_PY, 'snapkeep/timeutil.py': TIMEUTIL_PY,
        'snapkeep/snapshots.py': SNAPSHOTS_PY, 'snapkeep/manifest.py': MANIFEST_PY,
        'snapkeep/copier.py': COPIER_PY, 'snapkeep/staging.py': STAGING_PY,
        'snapkeep/retention.py': RETENTION_PY, 'snapkeep/verify.py': VERIFY_PY,
        'snapkeep/lockfile.py': LOCKFILE_PY, 'snapkeep/gc.py': GC_PY, 'snapkeep/report.py': REPORT_PY,
        'snapkeep/legacy_rsync.py': LEGACY_RSYNC_PY,
        'docs/decisions.md': DECISIONS_MD, 'docs/operations.md': OPERATIONS_MD, 'docs/cli.md': CLI_MD,
        'docs/snapshot-format.md': FORMAT_MD, 'docs/runbook-restore.md': RUNBOOK_MD,
        'docs/incidents.md': INCIDENTS_MD, 'docs/handoff.md': HANDOFF_MD,
        'tests/test_retention.py': VISIBLE_RETENTION,
    }
    ref1 = {
        'snapkeep/timeutil.py': TIMEUTIL_REF, 'lib/dates.sh': DATES_REF,
        'snapkeep/retention.py': RETENTION_REF, 'snapkeep/snapshots.py': SNAPSHOTS_REF,
        'snapkeep/staging.py': STAGING_REF, 'snapkeep/verify.py': VERIFY_REF,
        'snapkeep/lockfile.py': LOCKFILE_REF, 'snapkeep/gc.py': GC_REF,
        'bin/backup.sh': BACKUP_REF, 'bin/rotate.sh': ROTATE_REF, 'bin/restore.sh': RESTORE_REF,
        'docs/handoff.md': HANDOFF_REF1,
    }
    ref2 = {
        'config/snapkeep.json': CONFIG_JSON_2, 'snapkeep/config.py': CONFIG_PY_2,
        'snapkeep/retention.py': RETENTION_2, 'bin/rotate.sh': ROTATE_2,
        'docs/decisions.md': DECISIONS_2,
        'docs/handoff.md': HANDOFF_REF1 + '- 2026-09 retention 10/5/12/3 with a yearly tier; rotate --dry-run (lock-free).\n',
    }
    hidden1 = HIDDEN_COMMON + HIDDEN_STAGE1
    hidden2 = HIDDEN_COMMON + HIDDEN_STAGE1 + HIDDEN_STAGE2
    p = project('ho04_backup', 'infrastructure', 1 / 6, ['Bash', 'Python', 'JSON'], files, VISIBLE,
                [PROMPT1, PROMPT2], [ref1, ref2], [hidden1, hidden2], restart_after_first=True)
    p.update(difficulty='ultra', cluster='backup_reliability', predicted_single_pass=[.05, .30],
             budget_seconds=1800)
    return p
