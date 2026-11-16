# Security and backup design

**Status:** local runtime was inspected without exposing secrets or customer
records. The controls below are target requirements, not deployed controls.

## Current security assessment

- `.env` exists, is excluded by `.gitignore`, and has owner-only mode `0600`.
  `.env.example` contains placeholders. No secret values were read into this
  report.
- Compose currently binds frontend and backend host ports to loopback; the DB
  has no host port. This is a local-only deployment, not a public security
  boundary.
- Current backend app authentication uses Argon2 password hashing and HS256 JWT
  access tokens. The frontend stores the JWT in `localStorage`; an XSS issue
  could expose it. This is transitional behavior and conflicts with the target
  no-app-login requirement.
- The API and docs are not configured as a production private gateway. No
  tunnel, Access policy, HTTPS production endpoint, rate limit, backup job, or
  restoration drill was found.
- No production environment was inspected. Do not assume the local `.env`
  configuration is safe for deployment.
- The database volume is persistent. No customer/payment tables exist; one
  admin row was counted without reading its contents.

## Target access and application controls

1. Put HTTPS and a private identity gateway in front of the complete app and
   API. Require strong IdP MFA, session expiry/revocation, account recovery, and
   one explicitly authorized operator.
2. Keep the tunnel origin private; close public host ports for the app/API and
   never publish PostgreSQL. Do not rely on obscurity, CORS, or a frontend check
   as access control.
3. Remove application JWT/login only after gateway enforcement has been tested
   end-to-end from an authorized and unauthorized device. Remove token storage
   and app login as a separately approved application migration.
4. Keep secrets in a local owner-readable environment file for development and
   a protected secret store/runtime injection for production. Rotate
   credentials through a planned operation, not a diagnostic script.
5. Disable or protect Swagger/OpenAPI in production. Restrict CORS, methods,
   request sizes, and gateway routes to the minimum needed.
6. Apply least privilege to database roles: separate migration owner from
   application DML role; no superuser runtime. Keep DB network private.
7. Use patch management, pinned/reviewed image versions, TLS, firewall policy,
   encrypted host storage, monitoring, rate limits, and authentication/access
   logs without sensitive payloads.
8. Protect spreadsheet uploads and exports; validate size/content, stage
   imports, and neutralize spreadsheet formula injection on exports.

## Logging and privacy

Log timestamp, request ID, route, status, duration, and operational error
category. Do not log request bodies, passwords, JWTs, password hashes, DB URLs,
full customer exports, or payment credentials/references unless a documented
business need and retention policy justify a minimized field. Restrict log
access and retention. Audit financial changes separately from operational
logs, with append-only records and a verified actor.

## Backup and recovery proposal

- **Scope:** PostgreSQL logical backup (`pg_dump -Fc`) plus reviewed recovery
  configuration; do not copy a live volume as a substitute for a consistent
  backup.
- **Frequency/retention proposal:** daily encrypted backup, 7 daily + 4 weekly +
  12 monthly restore points, and object versioning/immutability where
  affordable. Confirm this retention and storage cost with the owner.
- **Encryption:** encrypt client-side before upload (for example with an
  `age` recipient or a managed KMS). Keep recovery/private keys outside the
  VPS and outside the backup bucket; maintain a separately protected recovery
  copy.
- **Off-site:** use a separate storage account/provider/region from the VPS.
  Check access policy, object lifecycle, deletion protection, and provider
  terms. Never upload `.env` or plaintext dumps.
- **Verification:** record backup timestamp, encrypted object size and checksum;
  periodically restore to an isolated temporary database and run schema,
  record-count, invoice/payment reconciliation, and application smoke checks.
  Do not overwrite the live volume during verification.
- **Recovery:** stop writes, preserve the original volume, restore to a new
  volume, validate integrity, then switch services through an approved change.
  Keep the original until the restored service is accepted.
- **Targets:** a daily backup gives a worst-case RPO near 24 hours, not a
  guarantee. Set RPO/RTO and whether WAL/PITR is necessary before production.

No backup automation is deployed or was run in this audit.

## Remaining risks and decisions

Owner must select gateway/identity provider, MFA/recovery policy, data residency
expectations, budget, RPO/RTO, retention, who can access backups, and incident
contacts. Public deployment is blocked until these controls and a restore drill
are accepted.
