"""Ultra existing-project: multi-currency, multi-timezone revenue reporting after a migration.

Synthetic data only. Python + SQLite/SQL views + a TypeScript dashboard formatter (node 22,
type stripping) + a bash nightly job. Stage 1 hides cross-component root causes (FX join
fan-out on republished rates, UTC month/day boundaries in the SQL view and in the TS
formatter, double counting on incremental re-runs in two separate loaders, and an export
that computes its own figures). Stage 2 changes the rules (corrections restate the original
month at the original rate, frozen closed months with explicit restatement, per-charge
half-away-from-zero rounding) while the report API, CSV export and ops paths stay stable.
"""
from tools.ho02_projects import project


def sub(text, old, new, count=1):
    assert text.count(old) == count, (old, text.count(old))
    return text.replace(old, new)


README = r'''# revenue-reporting
Monthly revenue per customer in EUR, built from two billing sources after the 2026-01
multi-currency / multi-timezone migration.

Layout:
- `revenue/` Python package: ingestion (`ingest.py`, `fx.py`), SQLite schema and views
  (`schema.sql`, `views.sql`, applied by `db.py` on every connect), the report service
  (`report.py`), the finance CSV export (`export.py`) and the ops CLI (`cli.py`).
- `dashboard/` TypeScript formatter run by node 22+ (type stripping): `render.mjs` reads the
  payload built by `report.dashboard_payload` on stdin and prints the dashboard JSON.
- `scripts/nightly.sh` nightly load of a drop directory.
- `docs/` decision log, contracts, operations, migration notes, finance notes.

Data flow:

    billing CSV (cumulative, nightly) --+
                                        +--> ingest.py --> charges --+
    ledger JSON (daily, retried) -------+                            +--> views.sql
    FX CSV (ECB, treasury republish) --> fx.py ------> fx_rates -----+   v_charges_eur
                                                                          |
                          report.py (monthly_revenue, drill-down) <-------+
                             |-- export.py --> finance CSV import (positional columns)
                             |-- cli.py    --> ops
                             +-- dashboard_payload --> node dashboard/render.mjs --> UI JSON

Conventions: stdlib only; UTC in storage; money as integer minor units and Decimal; SQL views
are recreated on connect; every decision goes into docs/decisions.md.

Tests: `python3 -m unittest discover -s tests -t .` (stdlib only, no network).

Local demo with the fixture drops:

    python3 -m revenue.cli init /tmp/rev.db
    python3 -m revenue.cli customers /tmp/rev.db fixtures/customers.csv
    python3 -m revenue.cli rates /tmp/rev.db fixtures/fx_rates.csv --loaded-at 2026-03-01T06:00:00Z
    python3 -m revenue.cli rates /tmp/rev.db fixtures/fx_treasury_2026-03-03.csv --loaded-at 2026-03-03T06:00:00Z
    bash scripts/nightly.sh /tmp/rev.db fixtures/drops/2026-03-31
    bash scripts/nightly.sh /tmp/rev.db fixtures/drops/2026-04-01
    python3 -m revenue.cli report /tmp/rev.db C-102
    python3 -m revenue.cli dashboard /tmp/rev.db C-105
'''

DECISIONS = r'''# Decision log
Newest entries win. Superseded entries stay for history.

## D-1 (2024-03) Reporting currency and storage
Revenue is reported in EUR. Amounts are stored as integer minor units (cents) of the charge
currency. Every currency we bill (EUR, CHF, USD, GBP) has two decimals.

## D-2 (2024-03) Revenue months are UTC calendar months
SUPERSEDED by D-4.

## D-3 (2024-09) Report and export formats
The report API returns revenue as a decimal string with exactly two decimals ('1234.50',
'-3.00'). Finance imports the CSV export with a macro that reads columns by position; see
docs/contracts.md.

## D-4 (2026-01, migration) Customer-local calendar
Customers carry an IANA time zone (customers.tz). A charge belongs to the calendar month and
the calendar day of its issue instant in the customer's time zone. This applies everywhere a
month or a day is derived for a customer: report API, drill-down, CSV export and the
dashboard. Timestamps are stored in UTC and never in local time.

## D-5 (2026-01, migration) FX conversion
A non-EUR charge converts at the rate whose effective_date is the latest one on or before the
charge's local business date (its customer-local day, D-4). EUR charges use rate 1. Rates are
decimal strings and conversions are exact decimal arithmetic.

## D-6 (2026-01) Rounding
Convert and sum each month at full precision, then round the monthly total once to whole
cents with banker's rounding (ROUND_HALF_EVEN). Per-charge EUR values shown in drill-downs
are rounded the same way but are informational. The CSV export shows exactly the report API's
figures.

## D-7 (2026-02) Republished rates
Treasury may republish a rate for an effective date that already has one (source
'treasury'). The row with the latest loaded_at is authoritative for that currency and date.
Superseded rows stay in fx_rates for audit: never delete or update them.

## D-8 (2026-02) Re-runnable ingestion
Every load can be re-run. The same file delivered twice is a no-op (ingest_batches), and
re-delivered data must never be counted twice (see D-9 and docs/operations.md).

## D-9 (2026-02) Charge identity
A charge is identified by (source, source_id). The billing system and the ledger allocate
ids independently and their ranges overlap. A re-delivered charge replaces the earlier
version of itself: billing fixes rows in place until the month is closed.

## D-10 (2026-03) Dashboard
Formatting lives in dashboard/format.ts, run by node. Python supplies every figure; the
dashboard only groups, labels and formats (no money arithmetic in TypeScript).

## D-11 (2026-03) Month-end close
close_month records the close in period_closes for audit. Reports do not freeze closed months
yet; freezing and restatement are planned with finance for Q2.

## D-12 (2026-03) Ledger corrections
The ledger will send corrections as records with kind 'correction' and corrects = the ledger
id of the corrected charge. Until the Q2 close project they are reported like any other
charge: in their own month, at their own date's rate.
'''

CONTRACTS = r'''# Contracts

## Report API (revenue/report.py)
Consumers: finance's notebook, the ops CLI and the dashboard. Rows are plain dicts. Consumers
read the keys listed here and ignore keys they do not know: new keys may be added, existing
keys never change name, type or meaning.

- `monthly_revenue(conn, customer_id)` -> list of `{month: 'YYYY-MM', revenue: str,
  charges: int}` ascending by month, one row per month that has charges. `revenue` is EUR
  with exactly two decimals (D-3, D-6); `charges` counts the charge rows in that month.
  Unknown customer: KeyError.
- `charges_in_month(conn, customer_id, month)` -> the charges that make up that month's row
  of monthly_revenue (same month attribution; a drill-down must reconcile with its month), as
  `{source, id, issued_at, currency, amount, eur, kind}` in issue order. `eur` is the charge
  converted to EUR and rounded to cents.
- `dashboard_payload(conn, customer_id)` / `render_dashboard(conn, customer_id)` -> dashboard
  JSON from dashboard/format.ts: `{customer, tz, currency, groups}`, groups newest month first,
  each `{month, label, revenue, charges, items}`; items `{id: 'source:source_id', day, eur,
  kind}`.
- `close_month(conn, customer_id, month, closed_at)` records month-end close (D-11);
  `closed_months(conn, customer_id)` lists closed months.
- Planned with the Q2 close project (not implemented): restatement of closed months. Rows of
  monthly_revenue will then also carry `restated: bool`, true once a closed month has been
  restated.

## CSV export (revenue/export.py, `python3 -m revenue.cli export`)
Finance's import macro reads columns by position. The header and column order are fixed:

    customer_id,month,revenue_eur,charges

One line per (customer, month) with charges, ordered by customer_id then month, '\n' line
endings, optional month filter. The figures are exactly those monthly_revenue returns; the
export never computes its numbers any other way.

## Inputs
Billing CSV export (one cumulative file per month, see docs/operations.md):

    invoice_id,customer_id,issued_at,currency,amount,type

`issued_at` is ISO 8601 UTC, `amount` a decimal string (negative for credits), `type` is
invoice or credit.

Ledger JSON feed: `{"feed": "ledger", "generated": ..., "records": [...]}` with records
`{id, customer, at, currency, amount, kind, corrects}`. `at` is ISO 8601 with an offset and is
stored as UTC. `kind` is invoice, credit or correction. `corrects` is null except for kind
correction, where it is the ledger `id` of the charge being corrected (D-12).

FX rates CSV: `currency,effective_date,rate,source` where rate is EUR per one unit of the
currency; `loaded_at` is the load time (or --loaded-at).

## Glossary
- charge: one row of `charges`: an invoice, a credit or (from the ledger) a correction.
- business date: the customer-local calendar day of a charge (D-4); the FX lookup key (D-5).
- month: the customer-local calendar month of a charge, 'YYYY-MM'.
- close: finance's month-end sign-off for one customer and month (period_closes).
- source: 'billing' or 'ledger'; source_id is only unique within its source (D-9).

## Examples
    >>> report.monthly_revenue(conn, 'C-102')
    [{'month': '2026-03', 'revenue': '660.00', 'charges': 3}]
    >>> print(export.export_csv(conn, month='2026-03'), end='')
    customer_id,month,revenue_eur,charges
    C-102,2026-03,660.00,3
'''

OPERATIONS = r'''# Operations
- Existing originals are immutable (fixtures/original.txt). Work only inside this project.
- Nightly job (cron 02:15 UTC): `scripts/nightly.sh <db> <drop-dir>`. It loads fx_*.csv, then
  billing_*.csv and ledger_*.json from the drop directory, then writes `<drop-dir>/revenue.csv`
  with the CSV export.
- The billing export is cumulative month-to-date and keeps the same file name all month:
  each night's billing_YYYY-MM.csv contains every charge of the month so far (including rows
  billing fixed in place), so it is loaded again every night. After month end the final file
  for the month is delivered once more on the 1st.
- The ledger sends one file per day. After a transfer timeout the sender re-sends the same
  content under a new name with a `.retryN` suffix (ledger_2026-03-05.retry1.json); both
  files end up in the drop directory.
- Treasury republishes rates now and then (D-7). Do not "clean up" fx_rates.
- Views are dropped and recreated on every connect (revenue/db.py), so a views.sql change
  takes effect on the next run without a migration. schema.sql uses IF NOT EXISTS.
- v_daily_activity feeds the ops load monitor (charges per customer-local day); keep it.
- The dashboard needs node 22+ with type stripping (`process.features.typescript`).
  `node dashboard/render.mjs --text < payload.json` prints the plain-text version for the
  weekly ops mail.

## Checks
- `python3 -m revenue.cli missing-rates <db>` exits 1 when a non-EUR charge has no rate.
- `python3 -m revenue.cli rates-board <db>` shows the authoritative rate per currency.
- `python3 -m revenue.cli batches <db>` lists the latest loads (file, source, rows).

## Incident log
- 2026-02-09: GBP rates for February were missing for two days; charges showed in
  missing-rates and the export silently skipped them. Rates loaded, nothing else changed.
- 2026-02-23: treasury republished the USD rate for 2026-02-16. Loaded as a new row (D-7).
- 2026-03-04: treasury republished the USD rate for 2026-03-01 (fx_treasury_2026-03-03.csv).
- 2026-03-29: Europe switched to summer time; no action needed, storage is UTC.
'''

MIGRATION = r'''# 2026-01 multi-currency migration (cut-over notes)

What changed:
- customers gained `tz` (IANA zone) and `billing_currency`. Before the migration every customer
  was EUR and reported in UTC months (D-2).
- charges was rebuilt: the old `amount_eur` column was replaced by `currency` + `amount_minor`
  and conversion moved to query time (views.sql joins fx_rates). The old table had
  UNIQUE(invoice_id); it was dropped because ledger ids overlap billing ids (D-9). A
  replacement identity constraint was planned but has not landed in schema.sql yet.
- fx_rates was imported from the ECB history; treasury republishes arrive as extra rows (D-7).
- The ledger JSON feed (second billing system) was connected. Its loader was written by a
  different team member than the billing CSV loader and shares no code with it.
- v_daily_activity was added for the ops load monitor.

Open items after cut-over:
- [ ] identity constraint for charges (see above)
- [x] dashboard: months and days follow D-4 (customer-local)
- [x] ledger timestamps normalised to UTC at load
- [x] legacy EUR-only report kept for the 2025 audit replay (revenue/legacy.py)
'''

FINANCE = r'''# Finance check-in, March 2026 (received 2026-04-03)
We reconcile a few customers by hand every month. March does not match.

- C-102 Nordwind Logistik (EUR): billing issued three invoices and one credit in March,
  660.00 EUR net, nothing after 18 March. The report showed 660.00 on the morning of the
  31st and 1,320.00 on 2 April.
- C-103 Hudson Print (USD): far above what billing issued. The three March invoices are
  1,385.00 USD in total.
- C-105 Tui Harbour Tours (USD, Auckland): the tour invoiced on the morning of 1 April (their
  time) is in March in the report. For them it is April revenue.
- We have not reconciled the Zurich and London customers yet.

Please do not change the export columns, our import macro reads them by position.
'''

HANDOFF = r'''# Handoff
Record changed behaviour, checks actually run and remaining limits here.

- 2026-03-28: added v_daily_activity for the ops load monitor; nightly job writes revenue.csv
  into the drop directory. Tests green.
'''

CONFIG = r'''"""Static configuration."""
import os
from pathlib import Path

REPORTING_CURRENCY = 'EUR'
NODE = os.environ.get('REVENUE_NODE', 'node')
DASHBOARD_ENTRY = Path(__file__).resolve().parents[1] / 'dashboard' / 'render.mjs'
'''

DB = r'''"""SQLite access: applies schema.sql, recreates views.sql, registers SQL functions."""
import sqlite3
from pathlib import Path

from .timeutil import local_day

HERE = Path(__file__).resolve().parent


def _local_day(ts, tz):
    return None if ts is None else local_day(ts, tz)


def connect(path=':memory:'):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    # local_day(utc_ts, tz) -> customer-local 'YYYY-MM-DD' (SQLite has no time zone support)
    conn.create_function('local_day', 2, _local_day, deterministic=True)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.executescript((HERE / 'schema.sql').read_text())
    conn.executescript((HERE / 'views.sql').read_text())
    conn.commit()
    return conn


if __name__ == '__main__':
    import sys
    connect(sys.argv[1]).close()
'''

SCHEMA = r'''-- Schema after the 2026-01 multi-currency migration (docs/migration-2026-01.md).
CREATE TABLE IF NOT EXISTS customers(
    id               TEXT PRIMARY KEY,
    name             TEXT NOT NULL,
    tz               TEXT NOT NULL DEFAULT 'UTC',   -- IANA zone (D-4)
    billing_currency TEXT NOT NULL DEFAULT 'EUR'
);

CREATE TABLE IF NOT EXISTS ingest_batches(
    id        INTEGER PRIMARY KEY,
    file_name TEXT NOT NULL,
    sha256    TEXT NOT NULL,
    source    TEXT NOT NULL,
    rows      INTEGER NOT NULL,
    loaded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS charges(
    id           INTEGER PRIMARY KEY,
    source       TEXT NOT NULL,       -- 'billing' (CSV export) or 'ledger' (JSON feed)
    source_id    TEXT NOT NULL,       -- id inside that source (D-9)
    customer_id  TEXT NOT NULL REFERENCES customers(id),
    issued_at    TEXT NOT NULL,       -- UTC 'YYYY-MM-DDTHH:MM:SSZ'
    currency     TEXT NOT NULL,
    amount_minor INTEGER NOT NULL,    -- cents of `currency`; credits are negative
    kind         TEXT NOT NULL DEFAULT 'invoice' CHECK (kind IN ('invoice', 'credit', 'correction')),
    corrects     TEXT,                -- ledger id amended by a 'correction' record (D-12)
    batch_id     INTEGER REFERENCES ingest_batches(id)
);
CREATE INDEX IF NOT EXISTS charges_by_customer ON charges(customer_id, issued_at);

CREATE TABLE IF NOT EXISTS fx_rates(
    currency       TEXT NOT NULL,
    effective_date TEXT NOT NULL,     -- 'YYYY-MM-DD'
    rate           TEXT NOT NULL,     -- EUR per unit, decimal string (never REAL)
    source         TEXT NOT NULL,     -- 'ecb' | 'treasury'
    loaded_at      TEXT NOT NULL      -- UTC time of the load
);
CREATE INDEX IF NOT EXISTS fx_by_currency ON fx_rates(currency, effective_date);

CREATE TABLE IF NOT EXISTS period_closes(
    customer_id TEXT NOT NULL,
    month       TEXT NOT NULL,
    closed_at   TEXT NOT NULL,
    PRIMARY KEY (customer_id, month)
);
'''

VIEWS = r'''-- Views are dropped and recreated on every connect (revenue/db.py).
DROP VIEW IF EXISTS v_monthly_revenue;
DROP VIEW IF EXISTS v_daily_activity;
DROP VIEW IF EXISTS v_fx_current;
DROP VIEW IF EXISTS v_charges_eur;

-- One row per charge with its month and the EUR conversion rate (D-4, D-5).
CREATE VIEW v_charges_eur AS
SELECT c.id                            AS charge_id,
       c.customer_id,
       c.source,
       c.source_id,
       c.kind,
       c.corrects,
       c.issued_at,
       date(c.issued_at)               AS business_date,
       strftime('%Y-%m', c.issued_at)  AS month,
       c.currency,
       c.amount_minor,
       CASE WHEN c.currency = 'EUR' THEN '1' ELSE r.rate END AS rate
FROM charges c
JOIN customers cu ON cu.id = c.customer_id
LEFT JOIN fx_rates r
       ON r.currency = c.currency
      AND r.effective_date = (SELECT MAX(x.effective_date) FROM fx_rates x
                              WHERE x.currency = c.currency
                                AND x.effective_date <= date(c.issued_at));

-- Monthly totals in exact EUR cents; read by the CSV export.
CREATE VIEW v_monthly_revenue AS
SELECT customer_id,
       month,
       COUNT(*)                               AS charges,
       SUM(amount_minor * CAST(rate AS REAL)) AS revenue_cents
FROM v_charges_eur
GROUP BY customer_id, month;

-- Ops rates board: the authoritative rate per currency for its latest effective date
-- (latest load wins, D-7). Read by `revenue.cli rates-board`.
CREATE VIEW v_fx_current AS
SELECT r.currency, r.effective_date, r.rate, r.source, r.loaded_at
FROM fx_rates r
WHERE r.rowid = (SELECT x.rowid FROM fx_rates x
                 WHERE x.currency = r.currency
                 ORDER BY x.effective_date DESC, x.loaded_at DESC, x.rowid DESC
                 LIMIT 1);

-- Ops load monitor: charges per customer-local day (counts only, no money).
CREATE VIEW v_daily_activity AS
SELECT c.customer_id,
       local_day(c.issued_at, cu.tz) AS day,
       COUNT(*)                      AS charges
FROM charges c
JOIN customers cu ON cu.id = c.customer_id
GROUP BY c.customer_id, day;
'''

TIMEUTIL = r'''"""Time helpers. Storage is always UTC; business dates are customer-local (D-4)."""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UTC_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(UTC_FORMAT)


def parse_utc(ts: str) -> datetime:
    return datetime.strptime(ts, UTC_FORMAT).replace(tzinfo=timezone.utc)


def to_utc_string(value: str) -> str:
    """Normalise an ISO 8601 timestamp with an explicit offset (or 'Z') to storage form."""
    text = value.strip()
    if text.endswith('Z'):
        text = text[:-1] + '+00:00'
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError(f'timestamp without offset: {value!r}')
    return moment.astimezone(timezone.utc).strftime(UTC_FORMAT)


def local_day(ts: str, tz: str) -> str:
    """Customer-local calendar day 'YYYY-MM-DD' of a stored UTC timestamp."""
    return parse_utc(ts).astimezone(ZoneInfo(tz or 'UTC')).strftime('%Y-%m-%d')


def month_bounds(month: str, tz: str) -> tuple:
    """UTC [start, end) of the customer-local calendar month 'YYYY-MM'."""
    zone = ZoneInfo(tz or 'UTC')
    year, mon = (int(part) for part in month.split('-'))
    start = datetime(year, mon, 1, tzinfo=zone)
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=zone)
    return (start.astimezone(timezone.utc).strftime(UTC_FORMAT),
            end.astimezone(timezone.utc).strftime(UTC_FORMAT))


def month_of(ts: str) -> str:
    """Revenue month under the 2024 rule (D-2, superseded). Only legacy.py uses this."""
    return ts[:7]
'''

MONEY = r'''"""Money helpers: integer minor units in, exact Decimal conversion, cents out (D-1, D-6)."""
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation


def parse_amount(text) -> int:
    """'1234.50' -> 123450. Two-decimal currencies only (D-1)."""
    try:
        value = Decimal(str(text).strip())
    except InvalidOperation as exc:
        raise ValueError(f'bad amount {text!r}') from exc
    minor = value * 100
    if minor != minor.to_integral_value():
        raise ValueError(f'more than two decimals: {text!r}')
    return int(minor)


def to_cents(exact) -> int:
    """Round an exact EUR-cent amount to whole cents: banker's rounding (D-6)."""
    return int(Decimal(exact).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def fmt_cents(cents: int) -> str:
    """123450 -> '1234.50', -300 -> '-3.00' (D-3)."""
    sign = '-' if cents < 0 else ''
    whole, frac = divmod(abs(int(cents)), 100)
    return f'{sign}{whole}.{frac:02d}'
'''

FX = r'''"""FX rates: loading and point lookups (D-5, D-7)."""
import csv
from decimal import Decimal, InvalidOperation

from .config import REPORTING_CURRENCY
from .money import fmt_cents, parse_amount, to_cents
from .timeutil import utc_now

COLUMNS = ('currency', 'effective_date', 'rate', 'source')


def load_rates(conn, path, loaded_at=None) -> int:
    """Append the rates of one CSV file. Rows are never updated or deleted (D-7)."""
    loaded_at = loaded_at or utc_now()
    rows = []
    with open(path, newline='') as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in COLUMNS[:3] if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f'{path}: missing columns {missing}')
        for row in reader:
            currency = row['currency'].strip().upper()
            day = row['effective_date'].strip()
            rate = row['rate'].strip()
            try:
                if Decimal(rate) <= 0:
                    raise ValueError
            except (InvalidOperation, ValueError):
                raise ValueError(f'bad rate {rate!r} for {currency} {day}') from None
            rows.append((currency, day, rate, (row.get('source') or 'ecb').strip(), loaded_at))
    conn.executemany('INSERT INTO fx_rates(currency, effective_date, rate, source, loaded_at) '
                     'VALUES (?, ?, ?, ?, ?)', rows)
    conn.commit()
    return len(rows)


def rate_on(conn, currency, day) -> Decimal:
    """Authoritative EUR rate for `currency` on business date `day` (D-5, D-7)."""
    if currency == REPORTING_CURRENCY:
        return Decimal(1)
    row = conn.execute('SELECT rate FROM fx_rates WHERE currency = ? AND effective_date <= ? '
                       'ORDER BY effective_date DESC, loaded_at DESC LIMIT 1', (currency, day)).fetchone()
    if row is None:
        raise LookupError(f'no FX rate for {currency} on {day}')
    return Decimal(row['rate'])


def missing_rates(conn):
    """Data-quality check: non-EUR charges with no rate on or before their business date."""
    rows = conn.execute('SELECT customer_id, source, source_id, currency, business_date '
                        'FROM v_charges_eur WHERE rate IS NULL ORDER BY currency, business_date')
    return [dict(row) for row in rows]


def rate_history(conn, currency):
    """Every stored row for one currency, oldest first, superseded rows included (D-7)."""
    rows = conn.execute('SELECT effective_date, rate, source, loaded_at FROM fx_rates WHERE currency = ? '
                        'ORDER BY effective_date, loaded_at', (currency.upper(),))
    return [dict(row) for row in rows]


def rates_board(conn):
    return [dict(row) for row in conn.execute('SELECT * FROM v_fx_current ORDER BY currency')]


def convert_preview(conn, currency, amount, day) -> str:
    """Ops helper: what `amount` of `currency` is worth in EUR on `day` ('12.34')."""
    return fmt_cents(to_cents(parse_amount(amount) * rate_on(conn, currency.upper(), day)))
'''

INGEST = r'''"""Load billing CSV exports and ledger JSON feeds into `charges` (docs/operations.md)."""
import csv
import hashlib
import json
from pathlib import Path

from .money import parse_amount
from .timeutil import to_utc_string, utc_now

KINDS = ('invoice', 'credit', 'correction')
BILLING_COLUMNS = ('invoice_id', 'customer_id', 'issued_at', 'currency', 'amount', 'type')


def file_digest(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def already_loaded(conn, path, digest) -> bool:
    """D-8: the same file delivered twice is a no-op."""
    row = conn.execute('SELECT 1 FROM ingest_batches WHERE file_name = ? AND sha256 = ?',
                       (Path(path).name, digest)).fetchone()
    return row is not None


def _open_batch(conn, path, digest, source) -> int:
    cur = conn.execute('INSERT INTO ingest_batches(file_name, sha256, source, rows, loaded_at) '
                       'VALUES (?, ?, ?, 0, ?)', (Path(path).name, digest, source, utc_now()))
    return cur.lastrowid


def _close_batch(conn, batch_id, rows):
    conn.execute('UPDATE ingest_batches SET rows = ? WHERE id = ?', (rows, batch_id))
    conn.commit()


def _kind(value) -> str:
    kind = (value or 'invoice').strip().lower()
    if kind not in KINDS:
        raise ValueError(f'unknown charge kind {value!r}')
    return kind


def _require_customer(conn, customer_id, path):
    if conn.execute('SELECT 1 FROM customers WHERE id = ?', (customer_id,)).fetchone() is None:
        raise ValueError(f'{Path(path).name}: unknown customer {customer_id!r} (load customers first)')


def load_customers(conn, path) -> int:
    with open(path, newline='') as fh:
        rows = [(r['id'].strip(), r['name'].strip(), (r.get('tz') or 'UTC').strip(),
                 (r.get('billing_currency') or 'EUR').strip().upper()) for r in csv.DictReader(fh)]
    conn.executemany('INSERT INTO customers(id, name, tz, billing_currency) VALUES (?, ?, ?, ?) '
                     'ON CONFLICT(id) DO UPDATE SET name = excluded.name, tz = excluded.tz, '
                     'billing_currency = excluded.billing_currency', rows)
    conn.commit()
    return len(rows)


def load_billing_csv(conn, path) -> int:
    """Billing system export. Returns the number of rows written."""
    digest = file_digest(path)
    if already_loaded(conn, path, digest):
        return 0
    try:
        batch_id = _open_batch(conn, path, digest, 'billing')
        written = 0
        with open(path, newline='') as fh:
            reader = csv.DictReader(fh)
            missing = [c for c in BILLING_COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f'{Path(path).name}: missing columns {missing}')
            for row in reader:
                if not (row['invoice_id'] or '').strip():
                    continue  # blank trailer lines from the billing export
                _require_customer(conn, row['customer_id'].strip(), path)
                conn.execute(
                    'INSERT INTO charges(source, source_id, customer_id, issued_at, currency, '
                    'amount_minor, kind, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    ('billing', row['invoice_id'].strip(), row['customer_id'].strip(),
                     to_utc_string(row['issued_at']), row['currency'].strip().upper(),
                     parse_amount(row['amount']), _kind(row['type']), batch_id))
                written += 1
        _close_batch(conn, batch_id, written)
        return written
    except Exception:
        conn.rollback()
        raise


def load_ledger_json(conn, path) -> int:
    """Ledger feed (JSON). Returns the number of records written."""
    digest = file_digest(path)
    if already_loaded(conn, path, digest):
        return 0
    doc = json.loads(Path(path).read_text())
    if doc.get('feed') != 'ledger':
        raise ValueError(f'{Path(path).name}: not a ledger feed')
    try:
        batch_id = _open_batch(conn, path, digest, 'ledger')
        records = []
        for rec in doc.get('records', []):
            records.append(('ledger', str(rec['id']), rec['customer'], to_utc_string(rec['at']),
                            rec['currency'].upper(), parse_amount(rec['amount']),
                            _kind(rec.get('kind')), rec.get('corrects'), batch_id))
        conn.executemany('INSERT INTO charges(source, source_id, customer_id, issued_at, currency, '
                         'amount_minor, kind, corrects, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         records)
        _close_batch(conn, batch_id, len(records))
        return len(records)
    except Exception:
        conn.rollback()
        raise


def batch_log(conn, limit=20):
    """Most recent loads first, for `revenue.cli batches`."""
    rows = conn.execute('SELECT id, file_name, source, rows, loaded_at FROM ingest_batches '
                        'ORDER BY id DESC LIMIT ?', (limit,))
    return [dict(row) for row in rows]


def ingest_path(conn, path) -> int:
    """Nightly entry point: dispatch one drop file by its type."""
    name = Path(path).name
    if name.endswith('.csv'):
        return load_billing_csv(conn, path)
    if name.endswith('.json'):
        return load_ledger_json(conn, path)
    raise ValueError(f'unsupported drop file {name}')
'''

REPORT = r'''"""Report service: monthly revenue per customer in EUR (docs/contracts.md)."""
import json
import subprocess
from decimal import Decimal

from . import config
from .money import fmt_cents, to_cents
from .timeutil import month_bounds


def _customer(conn, customer_id):
    row = conn.execute('SELECT id, name, tz, billing_currency FROM customers WHERE id = ?',
                       (customer_id,)).fetchone()
    if row is None:
        raise KeyError(customer_id)
    return row


def _charges(conn, customer_id):
    return conn.execute('SELECT * FROM v_charges_eur WHERE customer_id = ? '
                        'ORDER BY issued_at, charge_id', (customer_id,)).fetchall()


def exact_eur_cents(row) -> Decimal:
    """Exact EUR cents of one v_charges_eur row (D-5)."""
    if row['rate'] is None:
        raise LookupError(f"no FX rate for {row['currency']} on {row['business_date']}")
    return Decimal(row['amount_minor']) * Decimal(row['rate'])


def _charge_dict(row):
    return {'source': row['source'], 'id': row['source_id'], 'issued_at': row['issued_at'],
            'currency': row['currency'], 'amount': fmt_cents(row['amount_minor']),
            'eur': fmt_cents(to_cents(exact_eur_cents(row))), 'kind': row['kind']}


def monthly_revenue(conn, customer_id):
    """[{month, revenue, charges}] ascending by month (docs/contracts.md, D-6)."""
    _customer(conn, customer_id)
    totals = {}
    for row in _charges(conn, customer_id):
        exact, count = totals.get(row['month'], (Decimal(0), 0))
        totals[row['month']] = (exact + exact_eur_cents(row), count + 1)
    return [{'month': month, 'revenue': fmt_cents(to_cents(exact)), 'charges': count}
            for month, (exact, count) in sorted(totals.items())]


def charges_in_month(conn, customer_id, month):
    """Drill-down: the charges behind one month of monthly_revenue."""
    customer = _customer(conn, customer_id)
    start, end = month_bounds(month, customer['tz'])
    rows = conn.execute('SELECT * FROM v_charges_eur WHERE customer_id = ? AND issued_at >= ? '
                        'AND issued_at < ? ORDER BY issued_at, charge_id',
                        (customer_id, start, end)).fetchall()
    return [_charge_dict(row) for row in rows]


def close_month(conn, customer_id, month, closed_at):
    """Record month-end close (D-11). Figures are not frozen yet."""
    _customer(conn, customer_id)
    conn.execute('INSERT OR REPLACE INTO period_closes(customer_id, month, closed_at) VALUES (?, ?, ?)',
                 (customer_id, month, closed_at))
    conn.commit()


def closed_months(conn, customer_id):
    return [r[0] for r in conn.execute('SELECT month FROM period_closes WHERE customer_id = ? '
                                       'ORDER BY month', (customer_id,))]


def dashboard_payload(conn, customer_id):
    customer = _customer(conn, customer_id)
    items = [{'id': f"{row['source']}:{row['source_id']}", 'issued_at': row['issued_at'],
              'eur': fmt_cents(to_cents(exact_eur_cents(row))), 'kind': row['kind']}
             for row in _charges(conn, customer_id)]
    return {'customer': {'id': customer['id'], 'name': customer['name'], 'tz': customer['tz']},
            'months': monthly_revenue(conn, customer_id), 'items': items}


def render_dashboard(conn, customer_id):
    """Run dashboard/render.mjs (node) on the payload and return its JSON (D-10)."""
    payload = dashboard_payload(conn, customer_id)
    proc = subprocess.run([config.NODE, str(config.DASHBOARD_ENTRY)], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60)
    if proc.returncode != 0:
        raise RuntimeError(f'dashboard formatter failed: {proc.stderr.strip()[-500:]}')
    return json.loads(proc.stdout)


def year_to_date(conn, customer_id, year, through_month):
    """Sum of the reported monthly figures from January to `through_month` ('MM'), as '1234.50'."""
    months = [r for r in monthly_revenue(conn, customer_id)
              if r['month'][:4] == str(year) and r['month'][5:] <= through_month]
    cents = sum(int(r['revenue'].replace('.', '')) for r in months)
    return fmt_cents(cents)


def customer_overview(conn, month):
    """One line per customer for `month`: the monthly_revenue row, or zero when idle."""
    overview = []
    for customer in conn.execute('SELECT id, name, billing_currency FROM customers ORDER BY id').fetchall():
        row = next((r for r in monthly_revenue(conn, customer['id']) if r['month'] == month), None)
        overview.append({'customer_id': customer['id'], 'name': customer['name'],
                         'billing_currency': customer['billing_currency'], 'month': month,
                         'revenue': row['revenue'] if row else '0.00',
                         'charges': row['charges'] if row else 0})
    return overview
'''

EXPORT = r'''"""CSV export for finance's import macro (docs/contracts.md: columns are positional)."""
import csv
import io

from .money import fmt_cents

HEADER = ('customer_id', 'month', 'revenue_eur', 'charges')


def export_csv(conn, month=None) -> str:
    sql = 'SELECT customer_id, month, charges, revenue_cents FROM v_monthly_revenue'
    args = ()
    if month:
        sql += ' WHERE month = ?'
        args = (month,)
    sql += ' ORDER BY customer_id, month'
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(HEADER)
    for row in conn.execute(sql, args):
        cents = int(round(row['revenue_cents'] or 0))
        writer.writerow([row['customer_id'], row['month'], fmt_cents(cents), row['charges']])
    return out.getvalue()
'''

LEGACY = r'''"""Pre-migration (2024-2025) EUR-only monthly report.

Kept so the 2025 audit can be replayed against the archived single-currency database, whose
charges table still has the amount_eur column. Not wired into the API, the CLI or the export.
"""
from .timeutil import month_of


def legacy_monthly(conn, customer_id):
    months = {}
    for issued_at, amount_eur in conn.execute(
            'SELECT issued_at, amount_eur FROM charges WHERE customer_id = ?', (customer_id,)):
        key = month_of(issued_at)
        months[key] = months.get(key, 0) + amount_eur
    return {key: round(value / 100, 2) for key, value in sorted(months.items())}


def legacy_export(conn):
    """2025 export format (semicolon separated, comma decimals) for the audit replay only.

    Finance's current macro reads the comma-separated export in export.py; never point it here.
    """
    lines = ['kunde;monat;umsatz_eur']
    customers = [r[0] for r in conn.execute('SELECT DISTINCT customer_id FROM charges ORDER BY 1')]
    for customer_id in customers:
        for month, value in legacy_monthly(conn, customer_id).items():
            lines.append(f"{customer_id};{month};{value:.2f}".replace('.', ','))
    return '\n'.join(lines) + '\n'


def dedupe_rates(conn):
    """Migration dry-run helper (2026-01): keep one fx row per (currency, effective_date).

    Do NOT run against live data: superseded treasury rates must be kept (D-7).
    """
    conn.execute('DELETE FROM fx_rates WHERE rowid NOT IN '
                 '(SELECT MIN(rowid) FROM fx_rates GROUP BY currency, effective_date)')
    conn.commit()
'''

CLI = r'''"""Ops CLI: python3 -m revenue.cli <command> ..."""
import argparse
import json
import sys

from . import db, export, fx, ingest, report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='revenue')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init').add_argument('db')
    p = sub.add_parser('customers'); p.add_argument('db'); p.add_argument('file')
    p = sub.add_parser('rates'); p.add_argument('db'); p.add_argument('files', nargs='+')
    p.add_argument('--loaded-at')
    p = sub.add_parser('ingest'); p.add_argument('db'); p.add_argument('files', nargs='+')
    p = sub.add_parser('report'); p.add_argument('db'); p.add_argument('customer')
    p = sub.add_parser('drilldown'); p.add_argument('db'); p.add_argument('customer'); p.add_argument('month')
    p = sub.add_parser('export'); p.add_argument('db'); p.add_argument('--month')
    p = sub.add_parser('dashboard'); p.add_argument('db'); p.add_argument('customer')
    p = sub.add_parser('close'); p.add_argument('db'); p.add_argument('customer'); p.add_argument('month')
    p.add_argument('--at', required=True)
    p = sub.add_parser('quote'); p.add_argument('db'); p.add_argument('currency'); p.add_argument('amount')
    p.add_argument('day')
    p = sub.add_parser('overview'); p.add_argument('db'); p.add_argument('month')
    sub.add_parser('batches').add_argument('db')
    sub.add_parser('missing-rates').add_argument('db')
    sub.add_parser('rates-board').add_argument('db')
    a = ap.parse_args(argv)
    conn = db.connect(a.db)
    try:
        if a.cmd == 'customers':
            print(ingest.load_customers(conn, a.file))
        elif a.cmd == 'rates':
            for path in a.files:
                print(path, fx.load_rates(conn, path, loaded_at=a.loaded_at))
        elif a.cmd == 'ingest':
            for path in a.files:
                print(path, ingest.ingest_path(conn, path))
        elif a.cmd == 'report':
            print(json.dumps(report.monthly_revenue(conn, a.customer), indent=1))
        elif a.cmd == 'drilldown':
            print(json.dumps(report.charges_in_month(conn, a.customer, a.month), indent=1))
        elif a.cmd == 'export':
            sys.stdout.write(export.export_csv(conn, a.month))
        elif a.cmd == 'dashboard':
            print(json.dumps(report.render_dashboard(conn, a.customer), indent=1, ensure_ascii=False))
        elif a.cmd == 'close':
            report.close_month(conn, a.customer, a.month, a.at)
        elif a.cmd == 'quote':
            print(fx.convert_preview(conn, a.currency, a.amount, a.day))
        elif a.cmd == 'overview':
            for row in report.customer_overview(conn, a.month):
                print(f"{row['customer_id']:<8} {row['month']} {row['revenue']:>12} EUR {row['charges']:>4}  {row['name']}")
        elif a.cmd == 'batches':
            print(json.dumps(ingest.batch_log(conn), indent=1))
        elif a.cmd == 'missing-rates':
            gaps = fx.missing_rates(conn)
            print(json.dumps(gaps, indent=1))
            return 1 if gaps else 0
        elif a.cmd == 'rates-board':
            print(json.dumps(fx.rates_board(conn), indent=1))
    finally:
        conn.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
'''

FORMAT_TS = r'''// Dashboard formatter (D-10): turns the Python payload into month groups for the UI.
// Python supplies every figure; this module only groups, labels and formats.

export interface Customer { id: string; name: string; tz: string }
export interface MonthFigure { month: string; revenue: string; charges: number }
export interface PayloadItem { id: string; issued_at: string; eur: string; kind: string }
export interface DashboardPayload { customer: Customer; months: MonthFigure[]; items: PayloadItem[] }
export interface GroupItem { id: string; day: string; eur: string; kind: string }
export interface MonthGroup { month: string; label: string; revenue: string; charges: number; items: GroupItem[] }
export interface Dashboard { customer: string; tz: string; currency: 'EUR'; groups: MonthGroup[] }

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Month bucket 'YYYY-MM' of a charge. Payload timestamps are UTC ('...Z'). */
export function monthKey(issuedAt: string): string {
  const d = new Date(issuedAt);
  if (Number.isNaN(d.getTime())) throw new Error(`bad timestamp ${issuedAt}`);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

/** Day shown next to each charge in the activity list. */
export function dayLabel(issuedAt: string): string {
  return new Date(issuedAt).toISOString().slice(0, 10);
}

export function monthLabel(key: string): string {
  const [year, month] = key.split('-');
  return `${MONTH_NAMES[Number(month) - 1]} ${year}`;
}

/** Python decimal strings ('1234.5', '-3.00') -> '€1,234.50' / '-€3.00'. String math only. */
export function formatEur(value: string): string {
  const text = value.trim();
  const negative = text.startsWith('-');
  const [whole, frac = ''] = text.replace(/^[-+]/, '').split('.');
  const grouped = (whole || '0').replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return `${negative ? '-' : ''}€${grouped}.${(frac + '00').slice(0, 2)}`;
}

function emptyGroup(month: string): MonthGroup {
  return { month, label: monthLabel(month), revenue: formatEur('0.00'), charges: 0, items: [] };
}

export function buildDashboard(payload: DashboardPayload): Dashboard {
  const groups = new Map<string, MonthGroup>();
  const groupFor = (month: string): MonthGroup => {
    let group = groups.get(month);
    if (!group) {
      group = emptyGroup(month);
      groups.set(month, group);
    }
    return group;
  };
  for (const figure of payload.months) {
    const group = groupFor(figure.month);
    group.revenue = formatEur(figure.revenue);
    group.charges = figure.charges;
  }
  for (const item of payload.items) {
    groupFor(monthKey(item.issued_at)).items.push({
      id: item.id, day: dayLabel(item.issued_at), eur: formatEur(item.eur), kind: item.kind,
    });
  }
  const ordered = [...groups.values()].sort((a, b) => b.month.localeCompare(a.month));
  return { customer: payload.customer.name, tz: payload.customer.tz, currency: 'EUR', groups: ordered };
}

/** Plain-text rendering for the weekly ops mail (render.mjs --text). */
export function renderText(dashboard: Dashboard, maxItems = 5): string {
  const lines = [`${dashboard.customer} (${dashboard.tz}), figures in ${dashboard.currency}`];
  for (const group of dashboard.groups) {
    const count = group.charges === 1 ? '1 charge' : `${group.charges} charges`;
    lines.push(`${group.label.padEnd(9)} ${group.revenue.padStart(14)}  ${count}`);
    for (const item of group.items.slice(0, maxItems)) {
      lines.push(`  ${item.day}  ${item.eur.padStart(12)}  ${item.kind.padEnd(10)} ${item.id}`);
    }
    if (group.items.length > maxItems) lines.push(`  ... ${group.items.length - maxItems} more`);
  }
  return lines.join('\n') + '\n';
}
'''

RENDER = r'''// node dashboard/render.mjs < payload.json  ->  dashboard JSON on stdout
import { readFileSync } from 'node:fs';
import { buildDashboard, renderText } from './format.ts';

const payload = JSON.parse(readFileSync(0, 'utf8'));
const dashboard = buildDashboard(payload);
process.stdout.write(process.argv.includes('--text') ? renderText(dashboard) : JSON.stringify(dashboard));
'''

NIGHTLY = r'''#!/usr/bin/env bash
# Nightly load (cron 02:15 UTC): scripts/nightly.sh <db> <drop-dir>
# See docs/operations.md for what each drop file contains and how often it arrives.
set -euo pipefail
db="$(realpath -m "${1:?usage: nightly.sh <db> <drop-dir>}")"
drop="$(realpath -m "${2:?usage: nightly.sh <db> <drop-dir>}")"
cd "$(dirname "$0")/.."
shopt -s nullglob

lock="$db.lock"
if ! mkdir "$lock" 2>/dev/null; then
  echo "another nightly load holds $lock" >&2
  exit 75
fi
trap 'rmdir "$lock"' EXIT

for f in "$drop"/fx_*.csv; do
  python3 -m revenue.cli rates "$db" "$f"
done
for f in "$drop"/billing_*.csv "$drop"/ledger_*.json; do
  python3 -m revenue.cli ingest "$db" "$f"
done
python3 -m revenue.cli export "$db" > "$drop/revenue.csv.tmp"
mv "$drop/revenue.csv.tmp" "$drop/revenue.csv"
echo "nightly load done: $drop"
'''

CUSTOMERS_CSV = r'''id,name,tz,billing_currency
C-101,Alpenblick Hotels,Europe/Zurich,CHF
C-102,Nordwind Logistik,Europe/Berlin,EUR
C-103,Hudson Print,America/New_York,USD
C-104,Kestrel Analytics,Europe/London,GBP
C-105,Tui Harbour Tours,Pacific/Auckland,USD
C-106,Sakura Media,Asia/Tokyo,EUR
C-107,Prairie Seeds,America/Chicago,USD
'''

FX_CSV = r'''currency,effective_date,rate,source
CHF,2026-02-01,1.04,ecb
CHF,2026-03-01,1.06,ecb
USD,2026-02-01,0.91,ecb
USD,2026-03-01,0.92,ecb
USD,2026-03-16,0.93,ecb
GBP,2026-02-01,1.18,ecb
GBP,2026-03-01,1.19,ecb
'''

FX_TREASURY = r'''currency,effective_date,rate,source
USD,2026-03-01,0.925,treasury
'''

BILLING_0331 = r'''invoice_id,customer_id,issued_at,currency,amount,type
B-2001,C-101,2026-03-02T09:15:00Z,CHF,1200.00,invoice
B-2002,C-102,2026-03-03T10:00:00Z,EUR,480.00,invoice
B-2003,C-103,2026-03-04T14:30:00Z,USD,950.00,invoice
B-2004,C-102,2026-03-11T08:45:00Z,EUR,220.00,invoice
B-2005,C-103,2026-03-12T16:00:00Z,USD,310.00,invoice
B-2006,C-104,2026-03-13T11:20:00Z,GBP,640.00,invoice
B-2007,C-102,2026-03-18T13:00:00Z,EUR,-40.00,credit
B-2008,C-103,2026-03-18T17:10:00Z,USD,125.00,invoice
B-2009,C-104,2026-03-24T10:05:00Z,GBP,95.50,invoice
B-2011,C-106,2026-03-05T01:00:00Z,EUR,780.00,invoice
B-2012,C-107,2026-03-06T20:15:00Z,USD,145.00,invoice
B-2013,C-106,2026-03-16T23:30:00Z,EUR,210.00,invoice
B-2014,C-101,2026-03-17T08:00:00Z,CHF,-150.00,credit
B-2015,C-107,2026-03-21T15:40:00Z,USD,560.00,invoice
B-2016,C-106,2026-03-26T02:10:00Z,EUR,95.00,invoice
B-2017,C-104,2026-03-30T09:30:00Z,GBP,410.00,invoice
B-2018,C-107,2026-03-31T23:20:00Z,USD,88.00,invoice
'''

BILLING_0401 = BILLING_0331 + 'B-2010,C-101,2026-03-31T22:30:00Z,CHF,300.00,invoice\n'

LEDGER_0401 = r'''{
  "feed": "ledger",
  "generated": "2026-04-01T01:40:00Z",
  "records": [
    {"id": "L-5001", "customer": "C-105", "at": "2026-03-20T10:00:00+13:00", "currency": "USD",
     "amount": "400.00", "kind": "invoice", "corrects": null},
    {"id": "L-5002", "customer": "C-105", "at": "2026-04-01T08:30:00+13:00", "currency": "USD",
     "amount": "150.00", "kind": "invoice", "corrects": null},
    {"id": "2004", "customer": "C-104", "at": "2026-03-27T16:00:00+00:00", "currency": "GBP",
     "amount": "-20.00", "kind": "credit", "corrects": null}
  ]
}
'''

VISIBLE = r'''
import csv, io, json, subprocess, sys, tempfile
from pathlib import Path
from revenue import db, export, fx, ingest, report

CUSTOMERS = 'id,name,tz,billing_currency\nV1,Visible Zurich,Europe/Zurich,CHF\nV2,Visible Berlin,Europe/Berlin,EUR\n'
BILLING = ('invoice_id,customer_id,issued_at,currency,amount,type\n'
           'B-1,V1,2026-03-10T10:00:00Z,CHF,100.00,invoice\n'
           'B-2,V1,2026-03-12T10:00:00Z,CHF,50.00,invoice\n'
           'B-3,V2,2026-03-15T09:00:00Z,EUR,80.00,invoice\n'
           'B-4,V2,2026-04-14T09:00:00Z,EUR,-20.00,credit\n')


class Legacy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = str(self.root / 'rev.db')
        self.conn = db.connect(self.db_path)
        ingest.load_customers(self.conn, self.put('customers.csv', CUSTOMERS))
        fx.load_rates(self.conn, self.put('fx.csv', 'currency,effective_date,rate,source\nCHF,2026-03-01,1.10,ecb\n'),
                      loaded_at='2026-03-01T06:00:00Z')
        self.billing = self.put('billing_2026-03.csv', BILLING)
        self.assertEqual(ingest.ingest_path(self.conn, self.billing), 4)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def put(self, name, text):
        path = self.root / name
        path.write_text(text)
        return str(path)

    def rows(self, customer):
        return [(r['month'], r['revenue'], r['charges']) for r in report.monthly_revenue(self.conn, customer)]

    def test_monthly_revenue(self):
        self.assertEqual(self.rows('V1'), [('2026-03', '165.00', 2)])
        self.assertEqual(self.rows('V2'), [('2026-03', '80.00', 1), ('2026-04', '-20.00', 1)])
        with self.assertRaises(KeyError):
            report.monthly_revenue(self.conn, 'nobody')

    def test_export_layout(self):
        self.assertEqual(export.export_csv(self.conn),
                         'customer_id,month,revenue_eur,charges\nV1,2026-03,165.00,2\n'
                         'V2,2026-03,80.00,1\nV2,2026-04,-20.00,1\n')
        self.assertEqual(export.export_csv(self.conn, month='2026-04'),
                         'customer_id,month,revenue_eur,charges\nV2,2026-04,-20.00,1\n')

    def test_identical_file_is_a_noop(self):
        self.assertEqual(ingest.ingest_path(self.conn, self.billing), 0)
        self.assertEqual(self.rows('V1'), [('2026-03', '165.00', 2)])

    def test_drilldown(self):
        got = report.charges_in_month(self.conn, 'V1', '2026-03')
        self.assertEqual([(c['id'], c['amount'], c['eur']) for c in got],
                         [('B-1', '100.00', '110.00'), ('B-2', '50.00', '55.00')])

    def test_ledger_timestamps_stored_in_utc(self):
        doc = {'feed': 'ledger', 'generated': '2026-03-20T02:00:00Z', 'records': [
            {'id': 'L-1', 'customer': 'V2', 'at': '2026-03-19T10:00:00+01:00', 'currency': 'EUR',
             'amount': '12.00', 'kind': 'invoice', 'corrects': None}]}
        self.assertEqual(ingest.ingest_path(self.conn, self.put('ledger_2026-03-20.json', json.dumps(doc))), 1)
        row = self.conn.execute("SELECT issued_at FROM charges WHERE source = 'ledger'").fetchone()
        self.assertEqual(row[0], '2026-03-19T09:00:00Z')
        self.assertEqual(self.rows('V2'), [('2026-03', '92.00', 2), ('2026-04', '-20.00', 1)])

    def test_data_quality_helpers(self):
        self.assertEqual(fx.missing_rates(self.conn), [])
        self.assertEqual([(r['currency'], r['rate']) for r in fx.rates_board(self.conn)], [('CHF', '1.10')])
        self.assertEqual([b['rows'] for b in ingest.batch_log(self.conn)], [4])
        overview = report.customer_overview(self.conn, '2026-04')
        self.assertEqual([(o['customer_id'], o['revenue'], o['charges']) for o in overview],
                         [('V1', '0.00', 0), ('V2', '-20.00', 1)])
        days = self.conn.execute("SELECT day, charges FROM v_daily_activity WHERE customer_id = 'V1' ORDER BY day")
        self.assertEqual([tuple(r) for r in days], [('2026-03-10', 1), ('2026-03-12', 1)])

    def test_year_to_date(self):
        self.assertEqual(report.year_to_date(self.conn, 'V2', 2026, '04'), '60.00')
        self.assertEqual(report.year_to_date(self.conn, 'V2', 2026, '03'), '80.00')

    def test_unknown_customer_in_billing_file_is_rejected(self):
        bad = self.put('billing_2026-05.csv', 'invoice_id,customer_id,issued_at,currency,amount,type\n'
                                              'B-9,ZZ,2026-05-01T10:00:00Z,EUR,1.00,invoice\n')
        with self.assertRaises(ValueError):
            ingest.ingest_path(self.conn, bad)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM ingest_batches').fetchone()[0], 1)

    def test_quote_and_cli_report(self):
        from revenue import fx as fxmod
        self.assertEqual(fxmod.convert_preview(self.conn, 'chf', '10.00', '2026-03-05'), '11.00')
        out = subprocess.run([sys.executable, '-m', 'revenue.cli', 'report', self.db_path, 'V2'],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual([(r['month'], r['revenue']) for r in json.loads(out)],
                         [('2026-03', '80.00'), ('2026-04', '-20.00')])
'''

VISIBLE_DASH = r'''import json, subprocess, tempfile, unittest
from pathlib import Path
from revenue import db, fx, ingest, report


class Dashboard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / 'c.csv').write_text('id,name,tz,billing_currency\nV1,Visible Zurich,Europe/Zurich,CHF\n')
        (root / 'fx.csv').write_text('currency,effective_date,rate,source\nCHF,2026-03-01,1.10,ecb\n')
        (root / 'billing_2026-03.csv').write_text(
            'invoice_id,customer_id,issued_at,currency,amount,type\n'
            'B-1,V1,2026-03-10T10:00:00Z,CHF,1000.00,invoice\nB-2,V1,2026-03-12T10:00:00Z,CHF,50.00,invoice\n')
        self.conn = db.connect(str(root / 'rev.db'))
        ingest.load_customers(self.conn, str(root / 'c.csv'))
        fx.load_rates(self.conn, str(root / 'fx.csv'), loaded_at='2026-03-01T06:00:00Z')
        ingest.ingest_path(self.conn, str(root / 'billing_2026-03.csv'))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_render(self):
        dash = report.render_dashboard(self.conn, 'V1')
        self.assertEqual((dash['customer'], dash['tz'], dash['currency']), ('Visible Zurich', 'Europe/Zurich', 'EUR'))
        [group] = dash['groups']
        self.assertEqual((group['month'], group['label'], group['revenue'], group['charges']),
                         ('2026-03', 'Mar 2026', '€1,155.00', 2))
        self.assertEqual([(i['id'], i['day'], i['eur']) for i in group['items']],
                         [('billing:B-1', '2026-03-10', '€1,100.00'), ('billing:B-2', '2026-03-12', '€55.00')])

    def test_text_rendering(self):
        payload = json.dumps(report.dashboard_payload(self.conn, 'V1'))
        out = subprocess.run(['node', 'dashboard/render.mjs', '--text'], input=payload,
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out.splitlines()[:2], ['Visible Zurich (Europe/Zurich), figures in EUR',
                                                'Mar 2026       €1,155.00  2 charges'])

    def test_format_eur(self):
        code = ("import {formatEur} from './dashboard/format.ts'; "
                "console.log(JSON.stringify([formatEur('1234.5'), formatEur('-3.00'), formatEur('1000000.00')]))")
        out = subprocess.run(['node', '--input-type=module', '-e', code], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(out.stdout), ['€1,234.50', '-€3.00', '€1,000,000.00'])
'''

# ---------------------------------------------------------------- stage 1 reference
VIEWS_1 = sub(VIEWS, '''-- One row per charge with its month and the EUR conversion rate (D-4, D-5).
CREATE VIEW v_charges_eur AS
SELECT c.id                            AS charge_id,
       c.customer_id,
       c.source,
       c.source_id,
       c.kind,
       c.corrects,
       c.issued_at,
       date(c.issued_at)               AS business_date,
       strftime('%Y-%m', c.issued_at)  AS month,
       c.currency,
       c.amount_minor,
       CASE WHEN c.currency = 'EUR' THEN '1' ELSE r.rate END AS rate
FROM charges c
JOIN customers cu ON cu.id = c.customer_id
LEFT JOIN fx_rates r
       ON r.currency = c.currency
      AND r.effective_date = (SELECT MAX(x.effective_date) FROM fx_rates x
                              WHERE x.currency = c.currency
                                AND x.effective_date <= date(c.issued_at));
''', '''-- One row per charge with its customer-local month/day (D-4) and exactly one EUR rate:
-- the latest effective_date on or before the local business date, latest load wins (D-5, D-7).
CREATE VIEW v_charges_eur AS
SELECT c.id                                      AS charge_id,
       c.customer_id,
       c.source,
       c.source_id,
       c.kind,
       c.corrects,
       c.issued_at,
       local_day(c.issued_at, cu.tz)             AS business_date,
       substr(local_day(c.issued_at, cu.tz), 1, 7) AS month,
       c.currency,
       c.amount_minor,
       CASE WHEN c.currency = 'EUR' THEN '1' ELSE
            (SELECT r.rate FROM fx_rates r
              WHERE r.currency = c.currency
                AND r.effective_date <= local_day(c.issued_at, cu.tz)
              ORDER BY r.effective_date DESC, r.loaded_at DESC, r.rowid DESC
              LIMIT 1)
       END                                       AS rate
FROM charges c
JOIN customers cu ON cu.id = c.customer_id;
''')
VIEWS_1 = sub(VIEWS_1, '-- Monthly totals in exact EUR cents; read by the CSV export.',
              '-- Monthly totals in exact EUR cents (ad-hoc SQL only; the export uses report.monthly_revenue).')

SCHEMA_1 = sub(SCHEMA, "CREATE INDEX IF NOT EXISTS charges_by_customer ON charges(customer_id, issued_at);\n",
               "CREATE INDEX IF NOT EXISTS charges_by_customer ON charges(customer_id, issued_at);\n"
               "-- D-9: one row per (source, source_id); re-deliveries replace the earlier version.\n"
               "CREATE UNIQUE INDEX IF NOT EXISTS charges_identity ON charges(source, source_id);\n")

UPSERT = r'''UPSERT = ('INSERT INTO charges(source, source_id, customer_id, issued_at, currency, amount_minor, '
          'kind, corrects, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) '
          'ON CONFLICT(source, source_id) DO UPDATE SET customer_id = excluded.customer_id, '
          'issued_at = excluded.issued_at, currency = excluded.currency, '
          'amount_minor = excluded.amount_minor, kind = excluded.kind, '
          'corrects = excluded.corrects, batch_id = excluded.batch_id')
'''
INGEST_1 = sub(INGEST, "BILLING_COLUMNS = ('invoice_id', 'customer_id', 'issued_at', 'currency', 'amount', 'type')\n",
               "BILLING_COLUMNS = ('invoice_id', 'customer_id', 'issued_at', 'currency', 'amount', 'type')\n"
               "# D-8/D-9: re-delivered charges (cumulative billing files, ledger retries) replace themselves.\n" + UPSERT)
INGEST_1 = sub(INGEST_1, '''                conn.execute(
                    'INSERT INTO charges(source, source_id, customer_id, issued_at, currency, '
                    'amount_minor, kind, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    ('billing', row['invoice_id'].strip(), row['customer_id'].strip(),
                     to_utc_string(row['issued_at']), row['currency'].strip().upper(),
                     parse_amount(row['amount']), _kind(row['type']), batch_id))''',
               '''                conn.execute(UPSERT, (
                    'billing', row['invoice_id'].strip(), row['customer_id'].strip(),
                    to_utc_string(row['issued_at']), row['currency'].strip().upper(),
                    parse_amount(row['amount']), _kind(row['type']), None, batch_id))''')
INGEST_1 = sub(INGEST_1, '''        conn.executemany('INSERT INTO charges(source, source_id, customer_id, issued_at, currency, '
                         'amount_minor, kind, corrects, batch_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                         records)''', '''        conn.executemany(UPSERT, records)''')

EXPORT_1 = r'''"""CSV export for finance's import macro (docs/contracts.md: columns are positional)."""
import csv
import io

from .report import monthly_revenue

HEADER = ('customer_id', 'month', 'revenue_eur', 'charges')


def export_csv(conn, month=None) -> str:
    """Exactly the figures of report.monthly_revenue, one line per (customer, month)."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator='\n')
    writer.writerow(HEADER)
    for (customer_id,) in conn.execute('SELECT id FROM customers ORDER BY id').fetchall():
        for row in monthly_revenue(conn, customer_id):
            if month and row['month'] != month:
                continue
            writer.writerow([customer_id, row['month'], row['revenue'], row['charges']])
    return out.getvalue()
'''

LOCAL_TS = r'''function localParts(issuedAt: string, timeZone: string): Record<string, string> {
  const d = new Date(issuedAt);
  if (Number.isNaN(d.getTime())) throw new Error(`bad timestamp ${issuedAt}`);
  const fmt = new Intl.DateTimeFormat('en-US', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' });
  const parts: Record<string, string> = {};
  for (const part of fmt.formatToParts(d)) parts[part.type] = part.value;
  return parts;
}

/** Customer-local month bucket 'YYYY-MM' of a charge (D-4). Payload timestamps are UTC. */
export function monthKey(issuedAt: string, timeZone: string): string {
  const p = localParts(issuedAt, timeZone);
  return `${p.year}-${p.month}`;
}

/** Customer-local day shown next to each charge in the activity list (D-4). */
export function dayLabel(issuedAt: string, timeZone: string): string {
  const p = localParts(issuedAt, timeZone);
  return `${p.year}-${p.month}-${p.day}`;
}
'''
FORMAT_TS_1 = sub(FORMAT_TS, '''/** Month bucket 'YYYY-MM' of a charge. Payload timestamps are UTC ('...Z'). */
export function monthKey(issuedAt: string): string {
  const d = new Date(issuedAt);
  if (Number.isNaN(d.getTime())) throw new Error(`bad timestamp ${issuedAt}`);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, '0')}`;
}

/** Day shown next to each charge in the activity list. */
export function dayLabel(issuedAt: string): string {
  return new Date(issuedAt).toISOString().slice(0, 10);
}
''', LOCAL_TS)
FORMAT_TS_1 = sub(FORMAT_TS_1, '''    groupFor(monthKey(item.issued_at)).items.push({
      id: item.id, day: dayLabel(item.issued_at), eur: formatEur(item.eur), kind: item.kind,''',
                  '''    const tz = payload.customer.tz;
    groupFor(monthKey(item.issued_at, tz)).items.push({
      id: item.id, day: dayLabel(item.issued_at, tz), eur: formatEur(item.eur), kind: item.kind,''')

# ---------------------------------------------------------------- stage 2 reference
VIEWS_2 = sub(VIEWS_1, '''-- One row per charge with its customer-local month/day (D-4) and exactly one EUR rate:
-- the latest effective_date on or before the local business date, latest load wins (D-5, D-7).
CREATE VIEW v_charges_eur AS
SELECT c.id                                      AS charge_id,
       c.customer_id,
       c.source,
       c.source_id,
       c.kind,
       c.corrects,
       c.issued_at,
       local_day(c.issued_at, cu.tz)             AS business_date,
       substr(local_day(c.issued_at, cu.tz), 1, 7) AS month,
       c.currency,
       c.amount_minor,
       CASE WHEN c.currency = 'EUR' THEN '1' ELSE
            (SELECT r.rate FROM fx_rates r
              WHERE r.currency = c.currency
                AND r.effective_date <= local_day(c.issued_at, cu.tz)
              ORDER BY r.effective_date DESC, r.loaded_at DESC, r.rowid DESC
              LIMIT 1)
       END                                       AS rate
FROM charges c
JOIN customers cu ON cu.id = c.customer_id;
''', '''-- One row per charge with its customer-local month/day (D-4) and exactly one EUR rate:
-- the latest effective_date on or before the local business date, latest load wins (D-5, D-7).
-- Corrections are anchored on the charge they correct: its month and its rate (D-13).
CREATE VIEW v_charges_eur AS
WITH anchored AS (
    SELECT c.*, cu.tz, COALESCE(o.issued_at, c.issued_at) AS anchor_at
    FROM charges c
    JOIN customers cu ON cu.id = c.customer_id
    LEFT JOIN charges o
           ON c.kind = 'correction' AND o.source = c.source AND o.source_id = c.corrects
)
SELECT a.id                                      AS charge_id,
       a.customer_id,
       a.source,
       a.source_id,
       a.kind,
       a.corrects,
       a.issued_at,
       local_day(a.anchor_at, a.tz)              AS business_date,
       substr(local_day(a.anchor_at, a.tz), 1, 7) AS month,
       a.currency,
       a.amount_minor,
       CASE WHEN a.currency = 'EUR' THEN '1' ELSE
            (SELECT r.rate FROM fx_rates r
              WHERE r.currency = a.currency
                AND r.effective_date <= local_day(a.anchor_at, a.tz)
              ORDER BY r.effective_date DESC, r.loaded_at DESC, r.rowid DESC
              LIMIT 1)
       END                                       AS rate
FROM anchored a;
''')

SCHEMA_2 = SCHEMA_1 + '''
-- D-13: figures of a closed month as reported at close (or at the latest restatement).
CREATE TABLE IF NOT EXISTS period_snapshots(
    customer_id   TEXT NOT NULL,
    month         TEXT NOT NULL,
    revenue_cents INTEGER NOT NULL,
    charges       INTEGER NOT NULL,
    restated      INTEGER NOT NULL DEFAULT 0,
    taken_at      TEXT NOT NULL,
    PRIMARY KEY (customer_id, month)
);
'''

MONEY_2 = sub(MONEY, 'from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation',
              'from decimal import ROUND_HALF_UP, Decimal, InvalidOperation')
MONEY_2 = sub(MONEY_2, '''def to_cents(exact) -> int:
    """Round an exact EUR-cent amount to whole cents: banker's rounding (D-6)."""
    return int(Decimal(exact).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))''',
              '''def to_cents(exact) -> int:
    """Round one charge's exact EUR cents to whole cents, half away from zero (D-13)."""
    return int(Decimal(exact).quantize(Decimal(1), rounding=ROUND_HALF_UP))''')

REPORT_2 = sub(REPORT, '''def monthly_revenue(conn, customer_id):
    """[{month, revenue, charges}] ascending by month (docs/contracts.md, D-6)."""
    _customer(conn, customer_id)
    totals = {}
    for row in _charges(conn, customer_id):
        exact, count = totals.get(row['month'], (Decimal(0), 0))
        totals[row['month']] = (exact + exact_eur_cents(row), count + 1)
    return [{'month': month, 'revenue': fmt_cents(to_cents(exact)), 'charges': count}
            for month, (exact, count) in sorted(totals.items())]


def charges_in_month(conn, customer_id, month):
    """Drill-down: the charges behind one month of monthly_revenue."""
    customer = _customer(conn, customer_id)
    start, end = month_bounds(month, customer['tz'])
    rows = conn.execute('SELECT * FROM v_charges_eur WHERE customer_id = ? AND issued_at >= ? '
                        'AND issued_at < ? ORDER BY issued_at, charge_id',
                        (customer_id, start, end)).fetchall()
    return [_charge_dict(row) for row in rows]


def close_month(conn, customer_id, month, closed_at):
    """Record month-end close (D-11). Figures are not frozen yet."""
    _customer(conn, customer_id)
    conn.execute('INSERT OR REPLACE INTO period_closes(customer_id, month, closed_at) VALUES (?, ?, ?)',
                 (customer_id, month, closed_at))
    conn.commit()
''', '''def _live_months(conn, customer_id):
    """{month: (cents, charges)}: every charge rounded to cents, then summed (D-13)."""
    totals = {}
    for row in _charges(conn, customer_id):
        cents, count = totals.get(row['month'], (0, 0))
        totals[row['month']] = (cents + to_cents(exact_eur_cents(row)), count + 1)
    return totals


def monthly_revenue(conn, customer_id):
    """[{month, revenue, charges, restated}] ascending by month (docs/contracts.md, D-13).

    Closed months report their snapshot (taken at close or at the latest restatement).
    """
    _customer(conn, customer_id)
    live = _live_months(conn, customer_id)
    frozen = {r['month']: r for r in conn.execute(
        'SELECT * FROM period_snapshots WHERE customer_id = ?', (customer_id,))}
    rows = []
    for month in sorted(set(live) | set(frozen)):
        if month in frozen:
            snap = frozen[month]
            rows.append({'month': month, 'revenue': fmt_cents(snap['revenue_cents']),
                         'charges': snap['charges'], 'restated': bool(snap['restated'])})
        else:
            cents, count = live[month]
            rows.append({'month': month, 'revenue': fmt_cents(cents), 'charges': count,
                         'restated': False})
    return rows


def charges_in_month(conn, customer_id, month):
    """Drill-down: the charges behind one month of monthly_revenue (same attribution)."""
    _customer(conn, customer_id)
    rows = conn.execute('SELECT * FROM v_charges_eur WHERE customer_id = ? AND month = ? '
                        'ORDER BY issued_at, charge_id', (customer_id, month)).fetchall()
    return [_charge_dict(row) for row in rows]


def _is_closed(conn, customer_id, month):
    return conn.execute('SELECT 1 FROM period_closes WHERE customer_id = ? AND month = ?',
                        (customer_id, month)).fetchone() is not None


def close_month(conn, customer_id, month, closed_at):
    """Month-end close: freeze the month's figures as they are now (D-13)."""
    _customer(conn, customer_id)
    if _is_closed(conn, customer_id, month):
        return
    cents, count = _live_months(conn, customer_id).get(month, (0, 0))
    conn.execute('INSERT INTO period_closes(customer_id, month, closed_at) VALUES (?, ?, ?)',
                 (customer_id, month, closed_at))
    conn.execute('INSERT OR REPLACE INTO period_snapshots(customer_id, month, revenue_cents, charges, '
                 'restated, taken_at) VALUES (?, ?, ?, ?, 0, ?)', (customer_id, month, cents, count, closed_at))
    conn.commit()


def restate_month(conn, customer_id, month, restated_at=None):
    """Recompute a closed month from current data; it stays closed and is marked restated."""
    _customer(conn, customer_id)
    if not _is_closed(conn, customer_id, month):
        raise ValueError(f'{customer_id} {month} is not closed')
    cents, count = _live_months(conn, customer_id).get(month, (0, 0))
    conn.execute('INSERT OR REPLACE INTO period_snapshots(customer_id, month, revenue_cents, charges, '
                 'restated, taken_at) VALUES (?, ?, ?, ?, 1, ?)',
                 (customer_id, month, cents, count, restated_at or utc_now()))
    conn.commit()
''')
REPORT_2 = sub(REPORT_2, 'from .timeutil import month_bounds', 'from .timeutil import utc_now')
REPORT_2 = sub(REPORT_2, """    items = [{'id': f"{row['source']}:{row['source_id']}", 'issued_at': row['issued_at'],
              'eur': fmt_cents(to_cents(exact_eur_cents(row))), 'kind': row['kind']}""",
               """    items = [{'id': f"{row['source']}:{row['source_id']}", 'issued_at': row['issued_at'],
              'month': row['month'], 'eur': fmt_cents(to_cents(exact_eur_cents(row))),
              'kind': row['kind']}""")

FORMAT_TS_2 = sub(FORMAT_TS_1, 'export interface PayloadItem { id: string; issued_at: string; eur: string; kind: string }',
                  '// month: attributed month from Python (a correction belongs to the month it corrects).\n'
                  'export interface PayloadItem { id: string; issued_at: string; month?: string; eur: string; kind: string }')
FORMAT_TS_2 = sub(FORMAT_TS_2, 'groupFor(monthKey(item.issued_at, tz)).items.push({',
                  'groupFor(item.month ?? monthKey(item.issued_at, tz)).items.push({')

DECISIONS_2 = DECISIONS + '''
## D-13 (2026-04) Q2 close: corrections, frozen months, per-charge rounding
Supersedes D-6 (rounding), D-11 (freezing) and D-12 (corrections). A correction belongs to the
month of the charge it corrects and converts at that charge's rate. close_month freezes the
month's figures; restate_month recomputes a closed month, keeps it closed and marks it
restated. Every charge is converted and rounded to cents half away from zero before summing.
'''

# ---------------------------------------------------------------- hidden tests
HIDDEN_COMMON = r'''
import csv, io, json, subprocess, sys, tempfile
from pathlib import Path
from revenue import db, export, fx, ingest, report

CUSTOMERS = ('id,name,tz,billing_currency\n'
             'A1,Harbour Tours,Pacific/Auckland,USD\n'
             'E1,Berlin Freight,Europe/Berlin,EUR\n'
             'L1,Coast Media,America/Los_Angeles,EUR\n'
             'N1,Hudson Works,America/New_York,USD\n'
             'Z1,Alpine Rooms,Europe/Zurich,CHF\n')
BILLING = 'invoice_id,customer_id,issued_at,currency,amount,type\n'


def rec(ident, customer, at, currency, amount, kind='invoice', corrects=None):
    return {'id': ident, 'customer': customer, 'at': at, 'currency': currency, 'amount': amount,
            'kind': kind, 'corrects': corrects}


class Scenario(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db_path = self.root / 'revenue.db'
        self.conn = db.connect(str(self.db_path))
        ingest.load_customers(self.conn, self.put('customers.csv', CUSTOMERS))

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return str(path)

    def rates(self, name, lines, loaded_at):
        fx.load_rates(self.conn, self.put(name, 'currency,effective_date,rate,source\n' + lines), loaded_at=loaded_at)

    def billing(self, night, lines):
        return ingest.ingest_path(self.conn, self.put(f'{night}/billing_2026-03.csv', BILLING + lines))

    def ledger(self, name, records):
        doc = {'feed': 'ledger', 'generated': '2026-04-01T02:00:00Z', 'records': records}
        return ingest.ingest_path(self.conn, self.put(name, json.dumps(doc)))

    def months(self, customer):
        return {r['month']: (r['revenue'], r['charges']) for r in report.monthly_revenue(self.conn, customer)}


class Stage1(Scenario):
    # docs/decisions.md D-7 (latest-loaded republished rate wins, superseded rows kept) and
    # docs/contracts.md (drill-down reconciles with its month).
    def test_republished_rate_is_authoritative_and_kept(self):
        self.rates('fx1.csv', 'USD,2026-03-01,0.90,ecb\n', '2026-03-01T06:00:00Z')
        self.rates('fx2.csv', 'USD,2026-03-01,0.95,treasury\n', '2026-03-03T06:00:00Z')
        self.billing('n1', 'B-1,N1,2026-03-05T15:00:00Z,USD,100.00,invoice\n'
                           'B-2,N1,2026-03-10T15:00:00Z,USD,200.00,invoice\n')
        self.assertEqual(self.months('N1'), {'2026-03': ('285.00', 2)})
        self.assertEqual([c['eur'] for c in report.charges_in_month(self.conn, 'N1', '2026-03')], ['95.00', '190.00'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM fx_rates').fetchone()[0], 2)

    # docs/decisions.md D-4 (customer-local calendar month; D-2 is superseded).
    def test_month_follows_customer_time_zone(self):
        self.rates('fx.csv', 'USD,2026-03-01,0.90,ecb\n', '2026-03-01T06:00:00Z')
        self.billing('n1', 'B-1,A1,2026-03-10T00:00:00Z,USD,50.00,invoice\n'
                           'B-2,A1,2026-03-31T19:30:00Z,USD,100.00,invoice\n'
                           'B-3,L1,2026-03-01T05:00:00Z,EUR,10.00,invoice\n'
                           'B-4,L1,2026-04-01T03:00:00Z,EUR,40.00,invoice\n')
        self.assertEqual(self.months('A1'), {'2026-03': ('45.00', 1), '2026-04': ('90.00', 1)})
        self.assertEqual(self.months('L1'), {'2026-02': ('10.00', 1), '2026-03': ('40.00', 1)})
        self.assertEqual([c['id'] for c in report.charges_in_month(self.conn, 'A1', '2026-04')], ['B-2'])

    # docs/decisions.md D-5 (rate effective on the customer-local business date).
    def test_rate_uses_local_business_date(self):
        self.rates('fx.csv', 'USD,2026-03-01,0.90,ecb\nUSD,2026-03-16,0.80,ecb\n', '2026-03-16T06:00:00Z')
        self.billing('n1', 'B-1,A1,2026-03-15T12:00:00Z,USD,100.00,invoice\n'
                           'B-2,N1,2026-03-16T03:00:00Z,USD,100.00,invoice\n')
        self.assertEqual(self.months('A1'), {'2026-03': ('80.00', 1)})
        self.assertEqual(self.months('N1'), {'2026-03': ('90.00', 1)})

    # docs/operations.md (cumulative billing file reloaded nightly) and D-8/D-9 (no double
    # counting; a re-delivered charge replaces its earlier version).
    def test_cumulative_billing_file_reloaded_every_night(self):
        night1 = ('B-1,E1,2026-03-02T09:00:00Z,EUR,100.00,invoice\n'
                  'B-2,E1,2026-03-05T09:00:00Z,EUR,50.00,invoice\n')
        night2 = ('B-1,E1,2026-03-02T09:00:00Z,EUR,100.00,invoice\n'
                  'B-2,E1,2026-03-05T09:00:00Z,EUR,55.00,invoice\n'
                  'B-3,E1,2026-03-19T09:00:00Z,EUR,20.00,invoice\n')
        self.billing('n1', night1)
        self.billing('n2', night2)
        self.billing('n2', night2)
        self.assertEqual(self.months('E1'), {'2026-03': ('175.00', 3)})
        self.assertEqual([c['eur'] for c in report.charges_in_month(self.conn, 'E1', '2026-03')],
                         ['100.00', '55.00', '20.00'])

    # docs/operations.md (ledger retries re-sent under a .retryN name) and D-8.
    def test_ledger_retry_is_not_counted_twice(self):
        recs = [rec('L-1', 'E1', '2026-03-20T10:00:00+01:00', 'EUR', '30.00'),
                rec('L-2', 'E1', '2026-03-21T10:00:00+01:00', 'EUR', '-5.00', 'credit')]
        self.ledger('ledger_2026-03-20.json', recs)
        self.ledger('ledger_2026-03-20.retry1.json', recs)
        self.assertEqual(self.months('E1'), {'2026-03': ('25.00', 2)})

    # docs/decisions.md D-9 (identity is (source, source_id); billing and ledger ids overlap).
    def test_overlapping_ids_across_sources_are_distinct(self):
        self.billing('n1', '1001,E1,2026-03-03T09:00:00Z,EUR,10.00,invoice\n')
        self.ledger('ledger_2026-03-04.json', [rec('1001', 'E1', '2026-03-04T09:00:00Z', 'EUR', '20.00')])
        self.ledger('ledger_2026-03-05.json', [rec('1002', 'E1', '2026-03-05T09:00:00Z', 'EUR', '1.00')])
        self.assertEqual(self.months('E1'), {'2026-03': ('31.00', 3)})

    # docs/decisions.md D-4 (dashboard months and days are customer-local) and D-10.
    def test_dashboard_uses_customer_local_months_and_days(self):
        self.rates('fx.csv', 'USD,2026-03-01,0.90,ecb\n', '2026-03-01T06:00:00Z')
        self.billing('n1', 'B-1,A1,2026-03-10T00:00:00Z,USD,50.00,invoice\n'
                           'B-2,A1,2026-03-31T19:30:00Z,USD,100.00,invoice\n'
                           'B-3,L1,2026-03-01T05:00:00Z,EUR,10.00,invoice\n')
        groups = {g['month']: g for g in report.render_dashboard(self.conn, 'A1')['groups']}
        self.assertEqual(sorted(groups), ['2026-03', '2026-04'])
        self.assertEqual([(i['id'], i['day']) for i in groups['2026-04']['items']], [('billing:B-2', '2026-04-01')])
        self.assertEqual((groups['2026-04']['revenue'], groups['2026-04']['charges']), ('€90.00', 1))
        self.assertEqual([i['day'] for i in groups['2026-03']['items']], ['2026-03-10'])
        la = report.render_dashboard(self.conn, 'L1')['groups']
        self.assertEqual([(g['month'], [i['day'] for i in g['items']]) for g in la], [('2026-02', ['2026-02-28'])])

    # docs/contracts.md (the export carries exactly monthly_revenue's figures) and D-6.
    def test_export_carries_report_figures(self):
        self.rates('fx.csv', 'CHF,2026-03-01,1.15,ecb\nUSD,2026-03-01,0.90,ecb\n', '2026-03-01T06:00:00Z')
        self.billing('n1', 'B-1,Z1,2026-03-02T10:00:00Z,CHF,1000.00,invoice\n'
                           'B-2,Z1,2026-03-03T10:00:00Z,CHF,0.50,invoice\n'
                           'B-3,A1,2026-03-31T19:30:00Z,USD,100.00,invoice\n'
                           'B-4,E1,2026-03-31T22:30:00Z,EUR,12.00,invoice\n')
        rows = list(csv.reader(io.StringIO(export.export_csv(self.conn))))
        self.assertEqual(rows[0], ['customer_id', 'month', 'revenue_eur', 'charges'])
        expected = [[cid, r['month'], r['revenue'], str(r['charges'])]
                    for cid in ('A1', 'E1', 'L1', 'N1', 'Z1') for r in report.monthly_revenue(self.conn, cid)]
        self.assertEqual(rows[1:], expected)
        self.assertIn(['Z1', '2026-03', '1150.58', '2'], rows)
        self.assertEqual(export.export_csv(self.conn, month='2026-04').splitlines(),
                         ['customer_id,month,revenue_eur,charges', 'A1,2026-04,90.00,1', 'E1,2026-04,12.00,1'])

    # scripts/nightly.sh and docs/operations.md (the real nightly path re-loads the cumulative
    # file every night and writes the export).
    def test_nightly_job_reruns(self):
        n1 = 'B-1,E1,2026-03-02T09:00:00Z,EUR,100.00,invoice\n'
        n2 = n1 + 'B-2,E1,2026-03-20T09:00:00Z,EUR,30.00,invoice\n'
        self.put('drops/n1/billing_2026-03.csv', BILLING + n1)
        self.put('drops/n2/billing_2026-03.csv', BILLING + n2)
        for night in ('n1', 'n2', 'n2'):
            subprocess.run(['bash', 'scripts/nightly.sh', str(self.db_path), str(self.root / 'drops' / night)],
                           check=True, capture_output=True, text=True, timeout=60)
        self.assertEqual((self.root / 'drops/n2/revenue.csv').read_text(),
                         'customer_id,month,revenue_eur,charges\nE1,2026-03,130.00,2\n')
'''

HIDDEN_2 = HIDDEN_COMMON + r'''

class Stage2(Scenario):
    # stage-2 request (corrections belong to the corrected charge's month at its rate) and
    # docs/contracts.md (`corrects` = ledger id; drill-down uses the same attribution; dashboard
    # items carry 'source:source_id').
    def test_corrections_land_in_original_month_at_original_rate(self):
        self.rates('fx.csv', 'USD,2026-03-01,0.90,ecb\nUSD,2026-04-01,0.80,ecb\n', '2026-03-01T06:00:00Z')
        self.ledger('ledger_2026-04-02.json', [rec('L-10', 'N1', '2026-03-20T15:00:00Z', 'USD', '100.00'),
                                               rec('L-11', 'N1', '2026-04-02T15:00:00Z', 'USD', '50.00')])
        fixes = [rec('L-12', 'N1', '2026-04-10T15:00:00Z', 'USD', '-100.00', 'correction', 'L-10'),
                 rec('L-13', 'N1', '2026-04-12T15:00:00Z', 'USD', '-10.00', 'correction', 'L-11')]
        self.ledger('ledger_2026-04-12.json', fixes)
        self.ledger('ledger_2026-04-12.retry1.json', fixes)
        got = {r['month']: r['revenue'] for r in report.monthly_revenue(self.conn, 'N1')}
        self.assertEqual(got, {'2026-03': '0.00', '2026-04': '32.00'})
        self.assertEqual(sorted(c['id'] for c in report.charges_in_month(self.conn, 'N1', '2026-03')), ['L-10', 'L-12'])
        groups = {g['month']: g for g in report.render_dashboard(self.conn, 'N1')['groups']}
        self.assertEqual(sorted(i['id'] for i in groups['2026-03']['items']), ['ledger:L-10', 'ledger:L-12'])
        self.assertEqual(groups['2026-03']['revenue'], '€0.00')

    # stage-2 request (each charge converted and rounded half away from zero, then summed).
    def test_each_charge_rounded_half_away_from_zero(self):
        self.rates('fx.csv', 'CHF,2026-03-01,1.05,ecb\n', '2026-03-01T06:00:00Z')
        self.billing('n1', 'B-1,Z1,2026-03-02T10:00:00Z,CHF,0.10,invoice\n'
                           'B-2,Z1,2026-03-03T10:00:00Z,CHF,0.10,invoice\n'
                           'B-3,Z1,2026-04-02T10:00:00Z,CHF,-0.10,credit\n')
        self.assertEqual(self.months('Z1'), {'2026-03': ('0.22', 2), '2026-04': ('-0.11', 1)})
        self.assertEqual([c['eur'] for c in report.charges_in_month(self.conn, 'Z1', '2026-03')], ['0.11', '0.11'])
        self.assertIn('Z1,2026-03,0.22,2', export.export_csv(self.conn).splitlines())
        dash = report.render_dashboard(self.conn, 'Z1')
        self.assertEqual([(g['month'], g['revenue'], [i['eur'] for i in g['items']]) for g in dash['groups']],
                         [('2026-04', '-€0.11', ['-€0.11']), ('2026-03', '€0.22', ['€0.11', '€0.11'])])

    # stage-2 request (closed months frozen until restate_month, which keeps them closed) and
    # docs/contracts.md (the `restated` key; CSV layout unchanged).
    def test_closed_month_frozen_until_restated(self):
        self.billing('n1', 'B-1,E1,2026-03-02T09:00:00Z,EUR,100.00,invoice\n')
        report.close_month(self.conn, 'E1', '2026-03', '2026-04-03T08:00:00Z')
        night2 = ('B-1,E1,2026-03-02T09:00:00Z,EUR,120.00,invoice\n'
                  'B-2,E1,2026-03-28T09:00:00Z,EUR,30.00,invoice\n'
                  'B-3,E1,2026-04-02T09:00:00Z,EUR,10.00,invoice\n')
        self.billing('n2', night2)
        rows = {r['month']: r for r in report.monthly_revenue(self.conn, 'E1')}
        self.assertEqual((rows['2026-03']['revenue'], rows['2026-03']['charges'], rows['2026-03']['restated']),
                         ('100.00', 1, False))
        self.assertEqual((rows['2026-04']['revenue'], rows['2026-04']['restated']), ('10.00', False))
        self.assertEqual(export.export_csv(self.conn, month='2026-03'),
                         'customer_id,month,revenue_eur,charges\nE1,2026-03,100.00,1\n')
        report.restate_month(self.conn, 'E1', '2026-03')
        self.billing('n3', night2 + 'B-4,E1,2026-03-30T09:00:00Z,EUR,5.00,invoice\n')
        rows = {r['month']: r for r in report.monthly_revenue(self.conn, 'E1')}
        self.assertEqual((rows['2026-03']['revenue'], rows['2026-03']['charges'], rows['2026-03']['restated']),
                         ('150.00', 2, True))
        self.assertEqual(export.export_csv(self.conn).splitlines(),
                         ['customer_id,month,revenue_eur,charges', 'E1,2026-03,150.00,2', 'E1,2026-04,10.00,1'])

    # revenue/views.sql + docs/operations.md (v_daily_activity feeds the ops monitor; keep it).
    def test_ops_daily_activity_view_unchanged(self):
        self.billing('n1', 'B-1,A1,2026-03-10T00:00:00Z,EUR,5.00,invoice\n'
                           'B-2,A1,2026-03-31T19:30:00Z,EUR,5.00,invoice\n')
        got = self.conn.execute("SELECT day, charges FROM v_daily_activity WHERE customer_id = 'A1' ORDER BY day").fetchall()
        self.assertEqual([tuple(r) for r in got], [('2026-03-10', 1), ('2026-04-01', 1)])

    # revenue/cli.py + docs/contracts.md (CLI export is the same export; unrelated to the change).
    def test_cli_export_matches_api(self):
        self.billing('n1', 'B-1,E1,2026-03-02T09:00:00Z,EUR,100.00,invoice\n')
        self.conn.commit()
        out = subprocess.run([sys.executable, '-m', 'revenue.cli', 'export', str(self.db_path)],
                             capture_output=True, text=True, check=True).stdout
        self.assertEqual(out, export.export_csv(self.conn))
'''


def build():
    files = {
        'README.md': README,
        'docs/decisions.md': DECISIONS,
        'docs/contracts.md': CONTRACTS,
        'docs/operations.md': OPERATIONS,
        'docs/migration-2026-01.md': MIGRATION,
        'docs/finance-notes-2026-03.md': FINANCE,
        'docs/handoff.md': HANDOFF,
        'revenue/__init__.py': '"""Revenue reporting after the 2026-01 multi-currency migration."""\n',
        'revenue/config.py': CONFIG,
        'revenue/db.py': DB,
        'revenue/schema.sql': SCHEMA,
        'revenue/views.sql': VIEWS,
        'revenue/timeutil.py': TIMEUTIL,
        'revenue/money.py': MONEY,
        'revenue/fx.py': FX,
        'revenue/ingest.py': INGEST,
        'revenue/report.py': REPORT,
        'revenue/export.py': EXPORT,
        'revenue/legacy.py': LEGACY,
        'revenue/cli.py': CLI,
        'dashboard/format.ts': FORMAT_TS,
        'dashboard/render.mjs': RENDER,
        'scripts/nightly.sh': NIGHTLY,
        'fixtures/customers.csv': CUSTOMERS_CSV,
        'fixtures/fx_rates.csv': FX_CSV,
        'fixtures/fx_treasury_2026-03-03.csv': FX_TREASURY,
        'fixtures/drops/2026-03-31/billing_2026-03.csv': BILLING_0331,
        'fixtures/drops/2026-04-01/billing_2026-03.csv': BILLING_0401,
        'fixtures/drops/2026-04-01/ledger_2026-04-01.json': LEDGER_0401,
        'tests/test_dashboard.py': VISIBLE_DASH,
        '.gitignore': '__pycache__/\n*.pyc\nfixtures/drops/*/revenue.csv\n',
    }
    prompt1 = ('Monthly revenue per customer has been off for some customers since the multi-currency '
               'migration, and finance no longer trusts the March figures (their notes are in docs/). '
               'Make the numbers right. The report API and the CSV export finance imports have to keep working.')
    prompt2 = ('Finance changed the month-end process. Late corrections now come through the ledger feed as '
               'correction records that point at the original charge; they belong to the month of the charge '
               'they correct and are converted at that charge\'s rate, so a full credit brings it to exactly zero. '
               'Once a month is closed its figures must stay exactly as they were at close, whatever arrives later, '
               'until finance restates it with a new restate_month(conn, customer_id, month): that recomputes the '
               'month from current data, keeps it closed, and the report API then marks it as restated; the CSV '
               'export layout must not change. The auditors also want every charge converted and rounded to the '
               'cent, half away from zero, before summing, instead of rounding the monthly total. Everything else '
               'keeps working as it does today.')
    ref1 = {'revenue/views.sql': VIEWS_1, 'revenue/schema.sql': SCHEMA_1, 'revenue/ingest.py': INGEST_1,
            'revenue/export.py': EXPORT_1, 'dashboard/format.ts': FORMAT_TS_1}
    ref2 = {'revenue/views.sql': VIEWS_2, 'revenue/schema.sql': SCHEMA_2, 'revenue/money.py': MONEY_2,
            'revenue/report.py': REPORT_2, 'dashboard/format.ts': FORMAT_TS_2, 'docs/decisions.md': DECISIONS_2}
    p = project('u04_revenue', 'ai_data', 1/6, ['Python', 'SQL/SQLite', 'TypeScript', 'Bash', 'CSV', 'JSON'],
                files, VISIBLE, [prompt1, prompt2], [ref1, ref2], [HIDDEN_COMMON, HIDDEN_2],
                restart_after_first=True,
                owner_facts={'dashboard': 'follows the same customer-local calendar as the report (D-4)',
                             'corrections': 'corrects is always a ledger id of the same customer'})
    p.update(difficulty='ultra', cluster='revenue_reporting', predicted_single_pass=[0.05, 0.3],
             budget_seconds=1800)
    return p
