# Existing project audit

**Audit date:** 2026-11-15. **Scope:** repository source/configuration,
read-only Docker/runtime metadata, database catalog and count metadata. No
secrets or customer/payment contents were printed or read. No DB writes,
migrations, service restarts, image rebuilds, or deployments were performed.

## Existing architecture

- React 18 + TypeScript 5.7 + Vite 6 + Tailwind 3 frontend, currently served by
  Vite's development server.
- FastAPI 0.115 + SQLAlchemy 2.0 backend, Python 3.12.
- PostgreSQL 16 on Docker Compose.
- One API process and one frontend; no microservices.
- Existing app-level admin login uses Argon2 verification and HS256 JWT; JWT is
  stored in frontend localStorage.
- Backend routes: `/health`, `/api/auth/login`, `/api/auth/me`, and
  `/api/dashboard/summary`.
- Local Compose configuration binds frontend/backend to host loopback and keeps
  PostgreSQL on the private Compose network.

## Verified working

- `docker compose config --quiet`: passed.
- PostgreSQL container: healthy; backend `/health`: HTTP 200 with DB connected.
- Frontend root: HTTP 200.
- Frontend TypeScript and production Vite build: passed in a disposable
  container; only the existing Tailwind no-utility-classes warning appeared.
- `npm ls --depth=0`: passed in frontend container.
- `pip check`: passed in backend container.
- `.env` exists, is ignored by the current `.gitignore`, and has mode `0600`.
- Direct runtime evidence: Docker Engine 29.9.3, Compose 5.7.1, Node 20.20.2,
  Python 3.12.16.

These are local-development results only; they do not establish production
security, backup readiness, or customer workflows.

## Verified data and preservation state

- Existing named DB volume: `cable-manager-phase1_postgres_data`; it remains
  intact. The unrelated `open-webui` volume was not touched.
- Read-only catalog inspection found exactly one `public` table, `admin_users`,
  with columns `id`, `email`, `password_hash`, `is_active`, and `created_at`.
- A count query found one admin row. No row contents, customer data, or payment
  data were selected. There are no customer/invoice/payment tables.
- There is no Alembic configuration/version table. Startup calls
  `Base.metadata.create_all()`.
- `admin_users.email` has a unique index. There is an additional redundant
  ordinary index on the primary-key `id`.
- No migration or database change was made. Preserve the existing volume and
  row until an approved migration/retention plan exists.

## Incomplete or missing

- Customer, pricing, price history, billing period, invoice, payment,
  allocation, import batch, and audit models/routes are absent.
- Dashboard is a hard-coded zero-valued Phase 1 placeholder.
- No PWA manifest/service worker or offline policy.
- No automated frontend/backend tests. Backend test discovery returned exit 5
  with zero tests.
- No `package-lock.json`, Python lock file, Alembic, scripts, VS Code tasks, or
  architecture documentation existed at audit start.
- Frontend/backend Compose health checks are absent; only PostgreSQL has one.
- Frontend image uses `npm install`, range-based frontend dependencies, and no
  lockfile. Direct backend requirements are pinned, but transitive resolution
  is not locked.
- Existing README described the scaffold's app login as a product feature and
  listed Docker Desktop; it needed clarification for the single-user target and
  Linux environment.
- `.gitignore` excluded all of `.vscode`, which would also hide requested
  repository tasks.

## Security assessment

- Local ports are loopback-only and PostgreSQL is not host-published. No public
  deployment or access gateway exists.
- The current app login/JWT conflicts with the approved single-user product
  direction. It is transitional; removing it without a tested private gateway
  would weaken access protection.
- localStorage bearer-token storage increases impact of any frontend XSS.
- FastAPI docs/OpenAPI default routes need protection or disabling if deployed.
- There is no rate-limit/MFA gateway, encrypted off-site backup, restore test,
  production secret store, or incident/recovery procedure.
- `.env.example` is placeholder-only; never use placeholders in a deployed
  environment.
- Remote fonts are imported from Google Fonts; consider self-hosting or a
  system-font fallback to reduce third-party request/privacy/availability
  dependency.

## Reuse, refactor, defer, remove

**Reuse:** React/TypeScript shell and responsive CSS; FastAPI modular monolith;
SQLAlchemy/PostgreSQL; Docker Compose; current local health endpoints; existing
`.env` exclusion and DB volume.

**Refactor in approved follow-up:** replace startup `create_all()` with Alembic;
split route/domain concerns as business features grow; add strong constraints
and transaction services; add tests, lockfiles, service health checks, static
frontend production serving, and backup/recovery automation.

**Remove only after gateway approval and verification:** application login page,
JWT localStorage flow, and user-auth dependencies on target business routes.
Retain/migrate the existing admin row/table only according to an explicit data
retention decision. Do not remove roles/users that do not exist.

## Repository/tooling limitations

The workspace is not a Git repository; `git status` reports “not a git
repository.” A Git diff cannot be produced. Exact Phase 0 paths are listed in
the final report. No `.env` content was read into the audit.

## Recommendations

1. Resolve owner decisions in the roadmap before domain schema work.
2. Approve a gateway/provider and prove it protects both the app and API before
   removing app JWT authentication.
3. Design Alembic migrations and ledger constraints before customer/payment
   implementation; preserve the current volume.
4. Add tests and reproducible dependency lockfiles before importing business
   data.
5. Implement encrypted backups and a restore drill before remote production use.
