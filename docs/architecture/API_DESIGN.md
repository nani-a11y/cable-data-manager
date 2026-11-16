# API design

**Status:** current endpoints were inspected; target contract is proposed, not
implemented.

## Current API

The current FastAPI app exposes:

| Method and path | Current behavior |
|---|---|
| `GET /health` | Executes `SELECT 1`; returns status/database connectivity. |
| `POST /api/auth/login` | Validates email/password against the admin row and returns a JWT. |
| `GET /api/auth/me` | Returns the current JWT-authenticated admin. |
| `GET /api/dashboard/summary` | JWT-protected zero-valued Phase 1 placeholder. |
| `/docs`, `/openapi.json` | FastAPI's default interactive documentation/schema endpoints. |

The frontend currently targets `http://localhost:8000` by fallback and calls
`POST /api/auth/login`. CORS is environment-configured and currently defaults
to the local frontend origin. All of these are existing local scaffold behavior,
not the target authentication design.

## Target API boundary

Use same-origin routes under `/api/v1`. The complete application hostname and
all API routes must be covered by the private gateway policy. The backend and
database must not be directly reachable from the public Internet. There is no
app-level user login, registration, JWT session, or customer-facing identity.

If application audit entries need an actor, accept identity only from a
cryptographically verified gateway assertion or a private origin that cannot
be bypassed. Do not accept an arbitrary `X-User-Email`-style header from public
clients. Public API documentation is disabled or gateway-protected in
production. `/health` is local/internal-only or returns only minimal liveness;
it must not expose environment, database URLs, or secrets.

## Proposed resource surface

| Route family | Purpose |
|---|---|
| `GET/POST /api/v1/customers`, `GET/PATCH /api/v1/customers/{id}` | Search/create/update/archive customers with version conflicts. |
| `GET/POST /api/v1/pricing` and `/customers/{id}/prices` | Read defaults and append dated customer price history. |
| `GET /api/v1/billing-periods`, `POST /api/v1/billing-periods/{id}/invoices` | Preview/issue invoices idempotently for a period. |
| `GET /api/v1/invoices`, `GET /api/v1/invoices/{id}` | Query invoice snapshots and calculated balances. |
| `POST /api/v1/payments`, `POST /api/v1/payments/{id}/allocations` | Record receipts and allocate amounts transactionally. |
| `POST /api/v1/payments/{id}/reversals`, invoice adjustment routes | Append reasoned correction events; never overwrite history. |
| `POST /api/v1/import-batches`, `GET /{id}/preview`, `POST /{id}/approve` | Stage, inspect, and explicitly approve spreadsheet imports. |
| `GET /api/v1/reports/*`, `GET /api/v1/exports/*` | Read-only reports and operator-approved file exports. |

Route names are proposals; finalize with product workflows before implementation.
Use pagination for lists, stable ordering, server-side filtering, and bounded
export requests.

## Request, response, and error conventions

- JSON request/response models are validated by Pydantic. Use ISO 8601 timestamps
  with timezone offsets and explicit date-only period fields.
- Represent monetary values as decimal strings (`"1250.00"`), never JSON
  floating-point numbers. Include currency explicitly where values can vary.
- Return `201` for created resources, `200` for reads/updates, `204` for
  successful no-content actions, `400/422` for invalid input, `404` for missing
  resources, `409` for duplicate/concurrent/idempotency conflicts, and `503`
  for temporary dependency failures.
- Use one documented error envelope with a stable machine code, safe message,
  request ID, and field errors. Do not return stack traces, SQL, tokens, or
  personal data in error details.
- Add a request/correlation ID and structured operational logs that exclude
  credentials, request bodies containing PII, tokens, and payment details.
- Use `Idempotency-Key` for invoice issuance, payment creation, and import
  approval. Store key plus result atomically.
- Use entity versions/ETags and `If-Match` (or an explicit `version`) on edits
  where stale writes could overwrite changes. Return `409` on mismatch.

## Import/export and PWA behavior

Uploads are size/type limited, parsed into staging, malware/content-checked as
appropriate, and never applied until a preview and approval. The approval
transaction records accepted/rejected rows and a batch audit event.

Exports require gateway access and must avoid uncontrolled spreadsheet formula
execution (escape untrusted cells beginning with formula prefixes). Set
appropriate content type and no-store/no-cache policy for sensitive exports.
The service worker may cache versioned static shell assets only. Do not cache
customer, invoice, payment, or export responses in browser storage by default.
Offline mutation queues require a separately designed idempotency/conflict
model and are not part of this phase.

## Compatibility and deployment

Keep the API same-origin behind the gateway/proxy; CORS should be disabled or
restricted to explicitly approved origins. Configure request-size/time limits
at the proxy and application. The current `/api/auth/*` and JWT behavior remains
until the gateway replacement is separately implemented and accepted.
