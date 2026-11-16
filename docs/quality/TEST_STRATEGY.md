# Test strategy

**Status:** current build/dependency/health checks were executed during Phase 0.
No application test suite exists yet.

## Current evidence

- Frontend: `tsc -b && vite build` passed in an isolated disposable container
  using the existing frontend image; Vite reported the existing Tailwind
  “No utility classes” warning. This warning is consistent with the CSS-first
  UI but should be reviewed if utilities are introduced.
- Frontend dependency tree: `npm ls --depth=0` passed in the running frontend
  container.
- Backend dependency consistency: `pip check` passed.
- Backend discovery: `python -m unittest discover` found **0 tests** and
  returned exit code 5 (“NO TESTS RAN”). This is a coverage gap, not a passing
  test suite.
- Compose: `docker compose config --quiet` passed.
- Runtime: backend health and frontend returned HTTP 200; DB container was
  healthy. No service was rebuilt/restarted for this audit.

## Required test layers

1. **Unit/domain:** decimal rounding, effective-price selection, invoice
   uniqueness/idempotency, partial allocation, reversal calculations, import
   normalization/duplicate rules, and report totals. Use generated fixtures.
2. **Database integration:** Alembic upgrade from a reviewed baseline, unique
   constraints, no-overlap pricing, concurrent invoice issuance, transaction
   rollback, locked payment allocation, audit event atomicity, and forward
   migrations. Use a disposable test DB/volume only.
3. **API integration:** request validation/error contract, same-origin
   behavior, idempotency, optimistic conflicts, protected gateway boundary,
   export escaping, upload limits, no sensitive response/log leakage.
4. **Frontend:** accessible responsive customer/billing forms, form validation,
   import preview/approval, stale-response behavior, dashboard totals, and PWA
   static-only caching. Use mocked API responses and synthetic identities.
5. **End-to-end:** one operator journey from customer creation through price
   change, invoice, partial payment, correction, export, and next-period bill;
   verify prior outstanding is not duplicated. Test authorized and denied
   gateway devices.
6. **Recovery:** scheduled encrypted backup validation and restore into a
   separate DB, then compare schema/count/reconciliation outputs without
   printing business records.

## Safety and CI expectations

- Never connect automated tests to the live Compose database or production
  volume. Require a clearly named disposable test DB.
- Use fixed clocks and decimal fixtures; avoid nondeterministic dates/currency
  defaults.
- Run strict TypeScript build and backend tests on changes. Once a test runner
  is chosen/approved, fail CI on zero tests.
- Run dependency vulnerability review and lockfile consistency in a separate,
  reviewed tooling decision; do not auto-upgrade dependencies during a test run.
- Tests and logs must contain no real passwords, JWTs, hashes, customer PII, or
  payment records.

## Developer commands

- `bash scripts/preflight.sh`
- `bash scripts/validate-compose.sh`
- `bash scripts/compose-status.sh`
- `bash scripts/health-check.sh`
- `bash scripts/check-dependencies.sh` (requires running Compose services)
- `bash scripts/test-backend.sh` (currently reports no tests)
- `npm --prefix frontend run build` (requires host dependencies)

The safe scripts never install packages, start services, or mutate the database.
