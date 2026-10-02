#!/usr/bin/env python3
"""Source of eval/decisions/tier.jsonl. Edit labels here, then re-run to regenerate.

Each row: (domain, area, tier, peer, text). peer only for medium_tough ('astra'|'opus').
Splits alternate within each (tier, domain) group so dev and test are stratified.
"""
import json
from collections import defaultdict
from pathlib import Path

R, B, M, T = 'routine', 'bounded', 'medium_tough', 'tough'
C, K = 'coding', 'knowledge'

CASES = [
    # ---------------------------------------------------------------- routine
    (C, 'backend', R, None, 'Rename the config key `timeout_ms` to `timeout_s` in settings.py and update the two call sites.'),
    (C, 'docs', R, None, 'Fix the typo "recieve" in README.md and in the docstring of mailer.py.'),
    (C, 'infra', R, None, 'Bump the Node version in .nvmrc and the CI workflow from 20 to 22.'),
    (C, 'backend', R, None, 'Change the default page size constant from 20 to 50 in api/pagination.py.'),
    (C, 'frontend', R, None, 'Change the primary button colour from #2563eb to #1d4ed8 in theme.css.'),
    (C, 'backend', R, None, 'Add a debug log line when the cache is cleared in cache.py.'),
    (C, 'infra', R, None, 'Add .env.local and *.log to .gitignore.'),
    (C, 'backend', R, None, 'Remove the unused import of `itertools` from utils/dates.py.'),
    (C, 'frontend', R, None, 'Update the footer copyright year from 2025 to 2026.'),
    (C, 'backend', R, None, 'Pin requests to 2.33.1 in requirements.txt.'),
    (C, 'tests', R, None, 'Rename the test file test_Helpers.py to test_helpers.py.'),
    (C, 'backend', R, None, 'Make the error message "invalid input" in validators.py say "invalid email address" instead.'),
    (C, 'infra', R, None, 'Set the Docker image tag in docker-compose.yml from latest to 1.8.2.'),
    (C, 'frontend', R, None, 'Replace the placeholder text "Lorem ipsum" on the About page with the sentence in about.txt.'),
    (C, 'backend', R, None, 'Run the formatter over src/ and commit only the formatting changes.'),
    (C, 'docs', R, None, 'Add the missing link to CONTRIBUTING.md in the README table of contents.'),
    (C, 'backend', R, None, 'Increase the retry count constant MAX_RETRIES from 3 to 5.'),
    (C, 'frontend', R, None, 'Change the page title in index.html to "Acme Dashboard".'),
    (K, 'writing', R, None, 'Fix the spelling and punctuation in this meeting note without changing its meaning.'),
    (K, 'writing', R, None, 'Convert this bullet list of action items into a Markdown table with owner and due date columns.'),
    (K, 'writing', R, None, 'Rename all headings in the handbook from Title Case to sentence case.'),
    (K, 'data', R, None, 'Convert the attached CSV of contacts to JSON with the same fields.'),
    (K, 'writing', R, None, 'Translate the one-line status message "Deployment finished" into German and French.'),
    (K, 'writing', R, None, 'Shorten this 3-sentence product blurb to fit 140 characters.'),
    (K, 'data', R, None, 'Sort the glossary alphabetically and remove duplicate entries.'),
    (K, 'writing', R, None, 'Replace every occurrence of the old product name "Nimbus" with "Stratus" in the FAQ.'),
    (K, 'writing', R, None, 'Put today\'s date and version 2.3.1 at the top of the release notes file.'),
    (K, 'data', R, None, 'Round all prices in the spreadsheet column to two decimals.'),
    (C, 'backend', R, None, 'Delete the commented-out legacy function old_parse() from parser.py.'),
    (C, 'infra', R, None, 'Change the cron schedule of the nightly job from 02:00 to 03:00 UTC.'),
    # ---------------------------------------------------------------- bounded
    (C, 'backend', B, None, 'Fix the bug where the invoice export crashes on empty line items; add a regression test.'),
    (C, 'backend', B, None, 'Add a --json flag to the `report` CLI command that prints the same data as JSON.'),
    (C, 'backend', B, None, 'Add a GET /health endpoint that returns version and database connectivity.'),
    (C, 'frontend', B, None, 'Add a loading spinner to the orders table while data is fetched and show an error banner on failure.'),
    (C, 'backend', B, None, 'Validate that start_date is before end_date in the booking form handler and return a 400 with a clear message.'),
    (C, 'tests', B, None, 'Write unit tests for the currency formatting helpers, covering negative amounts and zero.'),
    (C, 'backend', B, None, 'Implement CSV download for the users list reusing the existing export service.'),
    (C, 'frontend', B, None, 'Make the settings page form remember unsaved changes and warn before navigating away.'),
    (C, 'backend', B, None, 'The password reset email link uses http instead of https in production; fix it and add a test.'),
    (C, 'infra', B, None, 'Add a GitHub Actions job that runs the linter on pull requests.'),
    (C, 'backend', B, None, 'Add pagination to the /projects endpoint following the pattern used by /users.'),
    (C, 'frontend', B, None, 'Add a dark-mode toggle to the header that uses the existing theme variables and persists in localStorage.'),
    (C, 'backend', B, None, 'Replace the deprecated datetime.utcnow() calls with timezone-aware equivalents across the module and fix the tests.'),
    (C, 'data', B, None, 'Write a script that deduplicates customer records in the CSV export by normalized email.'),
    (C, 'backend', B, None, 'The search endpoint ignores the `limit` parameter; make it respect limit with a max of 100.'),
    (C, 'frontend', B, None, 'Add client-side validation to the signup form: required fields, email format, password length.'),
    (C, 'infra', B, None, 'Add a Makefile target that builds the Docker image and runs the test suite inside it.'),
    (C, 'backend', B, None, 'Add structured JSON logging to the worker process using the existing logger config.'),
    (K, 'writing', B, None, 'Summarize this 12-page vendor contract into a one-page brief with the key obligations and dates.'),
    (K, 'writing', B, None, 'Draft a polite email to the customer explaining the two-day delay and the new delivery date.'),
    (K, 'writing', B, None, 'Write the "Getting started" section of the README from the existing install script and CLI help.'),
    (K, 'writing', B, None, 'Turn the merged pull requests of this sprint into a user-facing changelog.'),
    (K, 'writing', B, None, 'Write meeting minutes from this transcript with decisions and action items.'),
    (K, 'data', B, None, 'Build a pivot table of monthly revenue per region from the sales sheet and add a short commentary.'),
    (K, 'writing', B, None, 'Rewrite the error messages in the app to be friendlier while keeping them precise.'),
    (K, 'writing', B, None, 'Draft a job description for a senior backend engineer based on our team notes.'),
    (K, 'writing', B, None, 'Create a FAQ from the last 30 support tickets about billing.'),
    (K, 'writing', B, None, 'Prepare a 5-slide outline for the quarterly update from these bullet points.'),
    (C, 'backend', B, None, 'Cache the exchange-rate lookup for 10 minutes using the existing cache helper.'),
    (C, 'frontend', B, None, 'Show a toast notification after a successful profile save using our toast component.'),
    # ----------------------------------------------------------- medium_tough
    (C, 'backend', M, 'astra', 'Our websocket reconnect logic drops messages under load when the token refresh races the reconnect; find and fix the race across client, queue and auth modules.'),
    (C, 'backend', M, 'astra', 'Speed up the search endpoint: p95 is 2s; add caching and fix the N+1 queries across the ORM layer without changing results.'),
    (C, 'backend', M, 'astra', 'Jobs are sometimes processed twice when two workers pick them up; make the job queue claim atomic using the existing Postgres table.'),
    (C, 'backend', M, 'astra', 'Memory grows steadily in the ingestion service over 24 hours; find the leak and fix it.'),
    (C, 'backend', M, 'astra', 'Refactor the payment module to use the new PaymentProvider interface for both Stripe and PayPal without changing behaviour; keep all tests green.'),
    (C, 'backend', M, 'astra', 'Implement rate limiting per API key with a sliding window in Redis, integrated into the existing middleware chain.'),
    (C, 'backend', M, 'astra', 'The nightly ETL occasionally produces duplicated rows after a partial failure; make the load step idempotent.'),
    (C, 'infra', M, 'astra', 'Our flaky integration tests fail about 1 in 10 runs in CI only; find the timing dependency and make them deterministic.'),
    (C, 'backend', M, 'astra', 'Add optimistic locking to the inventory update path so concurrent orders cannot oversell stock.'),
    (C, 'data', M, 'astra', 'Rewrite the slow pandas aggregation over 50M rows to run in under a minute, preserving exact outputs.'),
    (C, 'backend', M, 'astra', 'Implement OAuth2 PKCE login in the CLI using our existing identity provider configuration.'),
    (C, 'backend', M, 'astra', 'Port the image resizing service from synchronous Flask to async FastAPI while keeping the API contract identical.'),
    (C, 'frontend', M, 'opus', 'Rebuild the dashboard layout to be fully responsive from 360px to 1440px with a collapsible sidebar and accessible keyboard navigation.'),
    (C, 'frontend', M, 'opus', 'Implement drag-and-drop reordering in the kanban board with smooth animations, optimistic updates and rollback on server error.'),
    (C, 'frontend', M, 'opus', 'Build an onboarding flow of four screens with progress indicator, validation and illustrations matching our design system.'),
    (C, 'frontend', M, 'opus', 'Make the data table handle 10,000 rows smoothly with virtualization, sticky headers and column resizing.'),
    (C, 'frontend', M, 'opus', 'Create an interactive pricing page with plan comparison, monthly/yearly toggle and animated transitions.'),
    (C, 'frontend', M, 'opus', 'Fix the accessibility issues reported by the audit across the checkout flow: focus order, contrast, ARIA labels and screen-reader announcements.'),
    (C, 'frontend', M, 'opus', 'Implement a rich-text comment editor with mentions, emoji and markdown shortcuts in our React app.'),
    (C, 'frontend', M, 'opus', 'Redesign the empty states and error pages across the app with consistent illustrations and helpful copy.'),
    (K, 'writing', M, 'opus', 'Write a technical explainer for customers on how our end-to-end encryption works, accurate enough for security reviewers.'),
    (K, 'research', M, 'astra', 'Compare three Python task-queue libraries on throughput, retries and operational complexity using their docs and published benchmarks, and recommend one for our workload.'),
    (K, 'writing', M, 'opus', 'Write the user guide for the new reporting feature with screenshots placeholders, examples and troubleshooting.'),
    (K, 'data', M, 'astra', 'Analyse six months of latency logs to find which endpoints regressed and correlate them with deploys.'),
    (K, 'writing', M, 'opus', 'Turn these interview notes from twelve customers into a synthesis of the top problems with supporting quotes.'),
    (K, 'research', M, 'astra', 'Reconcile the numbers in the finance report with the database export and explain every discrepancy.'),
    (K, 'writing', M, 'opus', 'Draft the landing-page copy and structure for our launch, in our brand voice, with three headline variants.'),
    (K, 'research', M, 'astra', 'Review our Terraform modules for cost waste and produce a prioritized list of concrete savings with estimates.'),
    (C, 'backend', M, 'astra', 'Add end-to-end tracing across the API gateway, the worker and the database layer using OpenTelemetry.'),
    (C, 'frontend', M, 'opus', 'Build a chart dashboard with filters, drill-down and export, using our charting library and design tokens.'),
    # ------------------------------------------------------------------ tough
    (C, 'architecture', T, None, 'Design a multi-tenant data architecture and migration plan to split our monolithic Postgres into per-tenant schemas with zero downtime.'),
    (K, 'research', T, None, 'Research and choose an approach for offline-first sync with conflict resolution for our mobile app, then design it.'),
    (C, 'architecture', T, None, 'Design how we move from a single-region deployment to active-active in two regions, including data consistency and failover.'),
    (C, 'security', T, None, 'Design the permission model for enterprise customers: roles, custom roles, resource-level access and audit, and how it fits our current API.'),
    (C, 'migration', T, None, 'Plan the migration of 400M events from MongoDB to ClickHouse without losing data or pausing ingestion.'),
    (C, 'architecture', T, None, 'Decide whether to break the billing module out of the monolith into a service, and design the boundary, contracts and rollout.'),
    (C, 'security', T, None, 'Design secrets management and key rotation for all services, replacing the environment-variable approach.'),
    (C, 'architecture', T, None, 'Design an event-driven architecture for order processing that guarantees exactly-once effects across payment, inventory and shipping.'),
    (C, 'architecture', T, None, 'Our app needs real-time collaboration on documents; choose between CRDTs and operational transforms and design the system.'),
    (C, 'migration', T, None, 'Plan and design the upgrade from Python 2-era Django 1.11 to Django 5 for a 300k-line codebase with minimal downtime.'),
    (C, 'irreversible', T, None, 'Design the procedure to permanently delete user data across all systems and backups to comply with GDPR erasure requests.'),
    (C, 'architecture', T, None, 'Design a plugin system for our desktop app that is sandboxed, versioned and supports third-party developers.'),
    (C, 'architecture', T, None, 'The system cannot keep up with 10x traffic next quarter; analyse the bottlenecks and design the scaling architecture.'),
    (C, 'security', T, None, 'Threat-model our public API and design the mitigations, including abuse prevention and authentication hardening.'),
    (C, 'research', T, None, 'Evaluate whether we should replace our in-house search with a vector database for semantic search, including a prototype design and cost model.'),
    (K, 'strategy', T, None, 'Write our 18-month technical strategy: platform bets, deprecations, hiring needs and risks.'),
    (K, 'research', T, None, 'Investigate why enterprise trial conversion dropped by 30% this year using product data, support tickets and churn interviews, and recommend changes.'),
    (K, 'strategy', T, None, 'Decide whether to build or buy our internal data platform, with a full analysis of options, costs and risks.'),
    (K, 'research', T, None, 'Research the regulatory requirements for offering our product in the EU health sector and design a compliance roadmap.'),
    (K, 'strategy', T, None, 'Propose a new pricing model for our API product, with modelling of revenue impact on existing customers.'),
    (K, 'research', T, None, 'Survey the current state of on-device LLM inference and recommend whether and how our app should use it.'),
    (C, 'architecture', T, None, 'Design the data model and APIs for a new ledger service that must be auditable and never lose or double-count money.'),
    (C, 'migration', T, None, 'Design the move from REST to GraphQL for our public API, including versioning, deprecation and client migration.'),
    (C, 'architecture', T, None, 'Design how the AI assistant feature will access customer data safely: retrieval, permissions, prompt-injection defenses and logging.'),
    (C, 'irreversible', T, None, 'Plan changing our primary keys from integers to UUIDs across 120 tables that other companies integrate with.'),
    (K, 'research', T, None, 'Research how competitors handle usage-based billing and design what we should adopt.'),
    (C, 'architecture', T, None, 'Design an observability strategy covering metrics, logs, traces, SLOs and on-call for our 40 services.'),
    (C, 'security', T, None, 'Design end-to-end encryption for user files such that even our own staff cannot read them, including key recovery.'),
    (K, 'strategy', T, None, 'Write the decision document on whether to open-source our SDK, with licensing, community and business implications.'),
    (C, 'research', T, None, 'We do not know why p99 latency spikes every few hours across unrelated services; investigate across the stack and propose an architectural fix.'),
]

# Peer-only rows: medium-tough implementation tasks labelled only for model choice.
PEER_ONLY = [
    (C, 'backend', M, 'astra', 'Implement a consistent-hashing shard router for our cache cluster with rebalancing on node changes.'),
    (C, 'backend', M, 'astra', 'Write a parser for our legacy fixed-width bank files into typed records with error recovery.'),
    (C, 'infra', M, 'astra', 'Convert our bash deployment scripts into a Python tool with dry-run, rollback and tests.'),
    (C, 'backend', M, 'astra', 'Implement a background job that reconciles subscription states with Stripe webhooks and fixes drift.'),
    (C, 'data', M, 'astra', 'Implement incremental materialized-view refreshes for the analytics tables with correctness tests.'),
    (C, 'frontend', M, 'opus', 'Build a map view with clustered markers, a detail drawer and smooth zoom transitions.'),
    (C, 'frontend', M, 'opus', 'Create an animated product tour overlay that highlights UI elements step by step.'),
    (C, 'frontend', M, 'opus', 'Implement a form builder UI where users drag fields onto a canvas and preview the form live.'),
    (K, 'writing', M, 'opus', 'Write the narrative case study of how a customer cut costs with our product, from interview notes.'),
    (C, 'frontend', M, 'opus', 'Polish the mobile layout of the checkout: spacing, typography, touch targets and micro-interactions.'),
]


def main() -> None:
    groups: dict = defaultdict(int)
    rows = []
    for i, (domain, area, tier, peer, text) in enumerate(CASES + PEER_ONLY):
        key = (tier, domain, i >= len(CASES))
        split = 'dev' if groups[key] % 2 == 0 else 'test'
        groups[key] += 1
        row = {'id': f'{tier[:1]}{i:03d}', 'domain': domain, 'area': area, 'text': text,
               'tier': tier if i < len(CASES) else None, 'peer': peer, 'split': split}
        rows.append(row)
    out = Path(__file__).parent / 'decisions' / 'tier.jsonl'
    out.write_text(''.join(json.dumps(r) + '\n' for r in rows))
    counts = defaultdict(int)
    for r in rows:
        counts[(r['tier'], r['split'])] += 1
    print(len(rows), 'rows', dict(counts))


if __name__ == '__main__':
    main()
