# Deployment design

**Status:** current local Compose state is verified. This is a target proposal;
no VPS, Cloudflare account, tunnel, DNS, or public deployment was created.

## Current local topology

Compose runs `frontend`, `backend`, and PostgreSQL 16. The frontend is a Vite
development server on host loopback port 5173; the backend is on loopback 8000;
PostgreSQL is only on the internal Compose network and uses the named
`postgres_data` volume. DB health is configured; frontend/backend Compose health
checks are absent. The frontend Dockerfile uses `npm install` and no workspace
lockfile exists. Local build/test/health shortcuts are in `scripts/`.

## Proposed VPS topology

- One maintained Linux VPS runs Docker Engine/Compose and the modular
  frontend/API/PostgreSQL stack. Avoid Kubernetes or microservices.
- A `cloudflared` service establishes an outbound tunnel. Access policy covers
  the full application hostname and `/api/*`; an origin proxy routes the
  static frontend and API privately. No public backend, frontend-dev, or DB
  port is published. Only explicitly required management access remains.
- Production frontend is a built static artifact, not Vite dev server.
- PostgreSQL uses a persistent named/data volume and private network. Application
  and migration roles are separate. A migration runs as a reviewed release
  step, not implicitly at every app startup.
- An independent scheduled job creates encrypted off-site logical backups and
  exposes success/failure/age without dumping data to logs.
- Health checks, bounded resource/log rotation, restart policies, and
  actionable alerting are configured. Service readiness is distinct from
  liveness.

## Private access alternatives

| Option | Benefits | Costs/maintenance | Fit |
|---|---|---|---|
| Cloudflare Tunnel + Access | Outbound tunnel avoids inbound app ports; browser HTTPS and identity policy work from mobile data/Wi-Fi without per-device VPN client; convenient PWA URL | Provider/account/domain dependency; plan, seat, and product terms can change; provider handles connection metadata; recovery and MFA policy must be owned | Recommended for evaluation if low-friction browser access is priority |
| Tailscale | Private mesh, device identity, no public web origin; mature device-to-device controls | Install/maintain client on each operator device; vendor account dependency; onboarding/revocation per device | Strong choice if all devices can run the client and maximum private-network simplicity is preferred |
| Self-hosted WireGuard | Minimal access-provider dependency and full control of tunnel keys | Operator owns endpoint, key distribution/revocation, clients, updates, and troubleshooting | Suitable only if owner accepts VPN operations |
| Public reverse proxy + HTTPS only | Standard web hosting and certificates | Publicly reachable origin/API; HTTPS alone does not authenticate the sole operator | Rejected without a separate strong gateway; conflicts with no app-login requirement |

No exact Cloudflare or VPS price is asserted. Confirm current Access plan/seat
limits, identity-provider support, domain cost, data processing, and storage
prices at the decision point. Cloudflare Access is a gateway identity, not an
application account. Prefer an IdP with MFA and a recovery path controlled by
the owner.

## Release, rollback, and operations

1. Build/test a tagged immutable artifact; use a lockfile and reviewed image
   versions/digests before production.
2. Take and verify a pre-release backup before schema changes.
3. Apply an explicit Alembic migration, then roll out the API and static frontend.
4. Check private health endpoints, gateway access from authorized and
   unauthorized clients, API behavior, and financial invariants.
5. If checks fail, route back to the prior image. Do not automatically reverse
   irreversible data migrations; use a reviewed forward fix or backup restore.
6. Monitor service health, disk capacity, backup age, tunnel/Access status, and
   failed authentication at the gateway without logging secrets.

Avoid automatic container updates that can silently change database or API
behavior. Choose an OS patch window and recovery contact. Production deployment
requires separate approval and a successful isolated restore test.
