# Product requirements

**Status:** Phase 0 audit baseline, 2026-11-15. This document distinguishes
verified current behavior from the proposed product.

## Product vision

Cable Manager is a private, dependable, mobile-friendly tool for one cable
operator (the user's father). The operator should use a browser on desktop,
laptop, or Android, optionally install the site as a PWA, and see one shared
business database from every device.

This is not a SaaS platform. Do not build customer accounts, self-registration,
multi-user administration, role systems, tenant management, microservices, or
Kubernetes. End-user access is controlled at the private remote-access gateway,
not by an application Admin login or JWT user-authentication flow.

## Functional requirements — target

1. Manage customer contact/service details and active/archive status.
2. Configure default pricing and retain dated customer-specific price history.
3. Create at most one immutable invoice per customer and billing period.
4. Record full and partial payments, allocate each payment to invoices, and
   calculate outstanding balances without duplicating previous balances.
5. Correct billing/payment mistakes through auditable reversal or adjustment
   transactions; do not destructively rewrite ledger history.
6. Import spreadsheets through staging, normalization, preview, duplicate
   detection, and explicit operator approval. Export filtered customers,
   invoices, and payment reports.
7. Provide a dashboard and reports derived from the central database.
8. Work responsively across mobile and desktop. PWA installation is in scope;
   offline writes are not assumed and must not silently queue financial changes.
9. Keep the application private behind the approved remote-access gateway,
   HTTPS, a private database network, and protected backups.

## Explicit exclusions

- Customer-facing logins or portals.
- Application user registration, application Admin login, JWT sessions, roles,
  or multiple operators.
- Public unauthenticated customer/payment APIs.
- SaaS tenancy, microservices, and Kubernetes.
- Automatic destructive edits, silent import merges, or speculative offline
  payment synchronization.

## Acceptance criteria

- One operator can safely use the same current customer/financial state from
  approved desktop and Android devices.
- A price change does not alter an already issued invoice.
- A customer/billing-period pair cannot receive duplicate invoices, including
  under concurrent requests.
- Partial allocations reduce the correct invoice balance exactly; a payment
  cannot be allocated beyond its available amount without an explicit
  overpayment-credit decision.
- A correction leaves an attributable, queryable reversal/adjustment trail.
- An import preview shows normalized values, errors, and duplicates before any
  persistent business change; approval is explicit and atomic.
- Backups are encrypted off-host and restoration has been exercised against an
  isolated database before production data is relied on.
- Static PWA resources may be cached; sensitive customer/payment responses are
  not cached offline by default.

## Non-functional requirements

- Financial values use decimal arithmetic and PostgreSQL `NUMERIC`.
- Schema changes are versioned migrations and are recoverable from backups.
- Security boundaries prevent direct internet access to origin services and
  PostgreSQL.
- Health checks expose only the minimum service state required for operations.
- Errors are visible and actionable without leaking credentials or customer
  data.
- Access remains usable over mobile networks; service availability and recovery
  targets are set before production.

## Verified current state

The repository is a local Phase 1 scaffold: a login/dashboard UI, FastAPI health
and authentication routes, and an `admin_users` table. Customer management,
pricing, invoices, payments, imports/exports, reports, and PWA support are not
implemented. See `docs/project/EXISTING_PROJECT_AUDIT.md`.

## Assumptions and owner decisions

- **Assumption:** one business and one trusted operator; no concurrent
  application users.
- **Decision required:** confirm business currency. The current UI formats INR,
  but that alone does not establish a product requirement.
- **Decision required:** billing timezone, service period boundaries, due-date
  policy, proration, invoice numbering, rounding, taxes/fees, and treatment of
  suspended customers.
- **Decision required:** payment allocation order, overpayments, refunds,
  reversals, cash/UPI/bank reference fields, and whether payment date or entry
  date controls reports.
- **Decision required:** source spreadsheet formats, duplicate-matching rules,
  initial opening-balance procedure, and which legacy records should be imported.
- **Decision required:** private gateway identity provider, recovery method,
  domain/account ownership, and acceptable vendor/data-processing relationship.
- **Decision required:** recovery point/time objectives and data-retention
  periods.

No business rules above are silently assumed by the schema or implementation.
