# Cable Manager — Copilot instructions

## Product and scope

Cable Manager is a private application for one cable-business operator. The
operator needs a responsive website/PWA, shared customer and billing data across
devices, monthly invoices, partial payments, Excel preview/import/export, and
reports.

Explicitly out of scope: customer accounts, registration, multiple application
users, roles, SaaS tenancy, microservices, and Kubernetes. The target has no
application Admin login page or JWT user login. Human access belongs at the
private remote-access gateway. The current repository still has transitional
admin/JWT code; do not remove or bypass it until the gateway replacement is
separately approved, implemented, and verified.

Read `docs/architecture/` and `docs/project/` before changing architecture or
business data. Documentation marks verified current behavior, proposed target
behavior, assumptions, and owner decisions separately.

## Current layout and architecture

- `frontend/`: React + TypeScript + Vite + Tailwind CSS; strict TypeScript is
  enabled. `frontend/src/api.ts` is the current HTTP client.
- `backend/app/`: one FastAPI modular monolith, SQLAlchemy models, settings,
  security functions, and route modules.
- `backend/requirements.txt`: pinned direct Python dependencies.
- `docker-compose.yml`: local frontend, backend, and PostgreSQL services.
- `docs/`: product and engineering decisions.
- `scripts/`: safe verification scripts; `.vscode/tasks.json` exposes them.

The current DB model is only `admin_users`; Alembic, customer/billing tables,
PWA service worker/manifest, and automated tests do not yet exist.

## Engineering conventions

- Keep changes surgical and preserve existing behavior unless a product decision
  explicitly changes it.
- Follow the existing TypeScript strictness and React patterns. Do not add
  `any`, TypeScript suppression comments, or relaxed compiler settings.
- Use Python type hints, Pydantic request/response models, SQLAlchemy 2 patterns,
  explicit transactions, and clear error responses.
- Use database migrations for future schema changes; do not use
  `Base.metadata.create_all()` as a production migration mechanism.
- Add focused tests for introduced behavior. Use sanitized synthetic fixtures;
  never use customer/payment exports or production credentials as fixtures.

## Database integrity rules

- Store money as fixed-precision `NUMERIC`/`Decimal`, never binary floating
  point. Serialize money as decimal strings in JSON.
- Issued invoices snapshot effective prices and are immutable. Enforce one
  invoice per customer and billing period with a database unique constraint.
- Keep payments and allocations as an auditable ledger. Corrections use
  append-only reversals/adjustments, not destructive edits or deletes.
- Calculate balances from invoices, allocations, and reversals. Do not roll
  previous balances into each new invoice or double-count them.
- Enforce positive amounts and allocation totals transactionally; lock affected
  rows and use unique/idempotency constraints to prevent concurrent duplicates.
- Preserve customer, invoice, payment, and audit history. Archive customers;
  do not cascade-delete financial records.
- Excel imports must stage rows, show normalized preview/errors/duplicates, and
  require explicit approval before applying changes.

## API and security

- Target API is same-origin under `/api/v1`; protect every customer/payment/API
  route and the web app with the approved private access gateway.
- Do not add application user registration, app-level JWT authentication, or
  public unauthenticated customer/payment routes.
- Never trust identity headers unless the gateway origin is private and the
  asserted identity is verified or otherwise cryptographically guaranteed.
- Do not store access tokens in browser localStorage in the target design.
- Keep PostgreSQL private; production origins must not expose DB/backend ports.
- Keep secrets in ignored local environment/secret stores. Never print `.env`,
  passwords, token values, hashes, customer PII, or payment details.
- Never disable TLS verification or weaken authentication to make a test pass.

## Local development and safe operations

- Use `scripts/preflight.sh`, `scripts/validate-compose.sh`,
  `scripts/compose-status.sh`, `scripts/health-check.sh`, and the VS Code tasks.
- Local Compose uses a persistent PostgreSQL volume. Never run `down -v`,
  volume/image pruning, database reset, or ad-hoc destructive SQL.
- Never rebuild/restart running services or modify environment secrets during an
  audit/validation task unless the user separately approves deployment work.
- Scripts must be deterministic, Linux-compatible, emit no secrets, and never
  install packages, start services, or alter database state without explicit
  user action.

## Definition of done

- Requirements and unresolved business decisions are reflected in docs.
- Code and directly related docs agree; migration/data effects are explicit.
- Focused tests, strict frontend build, dependency checks, and safe Compose
  validation pass where applicable. Report missing test coverage rather than
  claiming an empty test discovery is a pass.
- No credentials, real customer/payment data, or destructive side effects are
  included. Report exact changed paths and commands/results.
