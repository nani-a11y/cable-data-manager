# Implementation roadmap

**Status:** proposed sequence for architectural review. Phase 0 documentation
and safe automation are delivered by this audit; no broad refactor is included.

## Phase 0 — audit and decisions (complete)

- Record verified existing behavior, schema, runtime, preservation state, risks,
  and target design.
- Add repository-level Copilot instructions, safe local checks, and VS Code
  tasks.
- No app authentication removal, migration, service restart, or deployment.

## Phase 1 — access and operational foundation

1. **Owner decisions:** approve access provider/IdP/MFA/recovery, domain/VPS
   ownership, privacy/data processing, currency/timezone, billing rules, and
   backup RPO/RTO.
2. **Reproducibility:** approve and commit npm/Python lock strategy and pin
   reviewed runtime images. Add automated test framework only with an explicit
   dependency decision.
3. **Private gateway proof:** deploy only to a non-production test environment;
   verify authorized mobile/desktop access, unauthorized denial, API path
   coverage, no direct origin access, gateway session recovery, and HTTPS.
4. **Database change control:** create an Alembic baseline for the existing
   schema using a backup and a disposable copy. Preserve the current volume and
   admin row. No destructive migration.
5. **Auth transition:** only after step 3 passes and is approved, plan removal
   of app login/JWT from UI/API. Decide whether the existing admin table/row is
   retained, archived, or removed in a reviewed migration.
6. **Backup foundation:** automate encrypted off-site backup and validate a
   restore into a separate test DB before any business data is imported.

## Phase 2 — customer and pricing foundation

- Implement customer create/search/update/archive and stable customer numbers.
- Add pricing settings and effective-dated customer price history with no
  overlapping periods.
- Add audit events, optimistic concurrency, and database tests.
- Confirm import template and identity/matching rules before accepting legacy
  spreadsheets.

## Phase 3 — billing and invoices

- Implement billing periods and invoice preview/issuance with unique
  customer-period constraints, idempotency, and immutable price snapshots.
- Decide due-date, proration, rounding/tax, invoice numbering, and opening
  balance process first.
- Validate the one-invoice rule and no-previous-balance-double-counting with
  integration and property tests.

## Phase 4 — payments and reporting

- Record payment receipts and transactional allocations, including partial
  payments, reversals, overpayment policy, and audit events.
- Build balances and dashboard reports from ledger entries.
- Exercise concurrent posting, duplicate retries, correction workflows, and
  reconciliation.

## Phase 5 — spreadsheet and PWA workflows

- Implement import staging, validation, duplicate review, explicit approval,
  and export formula-safety.
- Add manifest/service worker and installability. Cache static shell only;
  require online confirmation for financial writes.
- Test on the operator's actual Android and desktop browsers.

## Phase 6 — production readiness and pilot

- Harden VPS, networks, gateway policy, observability, secrets, backups, restore
  drills, retention, and rollback.
- Migrate only owner-approved data after a dry run and reconciliation.
- Pilot with the operator; confirm billing totals and support/recovery process
  before using it as the system of record.

## Gated decisions and stop conditions

Do not implement production schema/migrations before currency, timezone,
billing/pricing rules, payment allocation/correction rules, import matching,
gateway choice, and recovery targets are approved. Stop if current data differs
from the inspected single-admin schema, a migration could lose data, gateway
controls cannot cover API paths, or restore validation fails.

The sequence does not authorize public deployment, account creation at a
provider, migration execution, deletion of the existing volume, or changes to
customer/payment records.
