# PHASE 4E.1 — DEPLOYMENT SECURITY VERIFICATION & INSTALLATION READINESS AUDIT REPORT

**Project:** Cable Data Manager  
**Repository:** `/home/kowshik/Downloads/cable-manager-phase1`  
**Committed Baseline (HEAD):** `4dff68eb5c41e4bf79b8a2ae7b0000dbc9854a48`  
**Execution Date:** November 16, 2026  
**Auditor:** Senior Linux Network Security Engineer, Docker Security Architect & DevOps Auditor  
**Status:** COMPLETE — RIGOROUSLY AUDITED & CORRECTED — PRODUCTION STOP GATE ENFORCED

---

## 1. Executive Summary & Verification Highlights

In Phase 4E.1, an adversarial security and accuracy audit was performed across the complete deployment architecture and operational documentation of Cable Data Manager.

The primary objective was to verify the accuracy and security of all deployment guides, specifically evaluating Docker network isolation, host firewall interactions (Docker iptables vs. UFW), HTTPS / TLS termination readiness, administrator initialization commands, and backup privilege boundaries.

### Key Audit Findings & Corrections:
1. **Docker iptables Bypass of UFW Formally Documented & Corrected (High Severity):**  
   Identified that standard UFW rules (e.g. `ufw allow from <subnet> to any port 8080`) do **not** reliably restrict Docker-published ports because Docker manipulates the `nat` table `PREROUTING` and filter `FORWARD` chains, bypassing UFW's `INPUT` chain. Corrected `docs/deployment/NETWORK_AND_TLS_GUIDE.md` to specify:
   - Primary defense: Explicit IP interface binding (`BIND_IP=<static_lan_ip>`).
   - Firewall defense: Direct `DOCKER-USER` chain iptables filtering.
2. **Mode B (Plain HTTP over Wi-Fi/LAN) Explicitly Disapproved (High Severity):**  
   Plain HTTP is **strictly prohibited** for shop Wi-Fi / LAN usage. Transmitting unencrypted customer financial ledgers, Khata balances, and JWT tokens across wireless airwaves exposes the business to local packet interception. Mode B is documented as requiring mandatory HTTPS termination.
3. **Mode A (Localhost Only) Verified as the Sole Approved Deployment Baseline:**  
   Verified that `docker-compose.prod.yml` default binding `- "${BIND_IP:-127.0.0.1}:${PROD_PORT:-8080}:8080"` guarantees localhost-only exposure. Backend port 8000 and PostgreSQL port 5432 have zero published host ports.
4. **Command Accuracy Validated Against Source Code:**  
   Every installation, migration, CLI password reset, backup, and restore command in `docs/deployment/` was cross-checked against actual repository source code. Zero stale or non-existent arguments exist.
5. **Docker Socket Privilege Boundaries Reaffirmed:**  
   Documented unequivocally that `/run/docker.sock` access remains root-equivalent on the host. Systemd sandboxing directives mitigate host process breakout but do not eliminate the root-equivalent authority of the Docker daemon.

---

## 2. Initial Git Baseline & Working Tree State

- **Repository Path:** `/home/kowshik/Downloads/cable-manager-phase1`
- **Active Branch:** `main`
- **Committed Baseline HEAD:** `4dff68eb5c41e4bf79b8a2ae7b0000dbc9854a48` (`feat(phase3): complete customer collection register and financial engine`)
- **Staged Files:** `0` (Zero files staged)
- **Tracked Modifications (8 files):**
  - `.env.example`
  - `backend/app/config.py`
  - `backend/app/main.py`
  - `backend/app/routes/auth.py`
  - `backend/app/security.py`
  - `backend/tests/test_config.py`
  - `docs/architecture/SECURITY_AND_BACKUP.md`
  - `frontend/src/api.ts`
- **Untracked Additions (18 items):**
  - `backend/Dockerfile.prod`
  - `backend/app/cli.py`
  - `backend/app/rate_limiter.py`
  - `backend/tests/test_backup_restore.py`
  - `backend/tests/test_cli.py`
  - `backend/tests/test_rate_limiting.py`
  - `docker-compose.prod.yml`
  - `docs/deployment/` (`PRODUCTION_INSTALLATION_GUIDE.md`, `NETWORK_AND_TLS_GUIDE.md`, `BACKUP_OPERATIONS_GUIDE.md`, `UPGRADE_AND_RECOVERY_GUIDE.md`, `OPERATOR_QUICK_START.md`)
  - `docs/production-packaging.md`
  - `docs/quality/PHASE_4C_1_BACKUP_SAFETY_AUDIT.md`
  - `docs/quality/PHASE_4D_1_SYSTEMD_SECURITY_AUDIT.md`
  - `docs/quality/PHASE_4D_2_DOCKER_PRIVILEGE_AND_TEST_AUDIT.md`
  - `docs/quality/PHASE_4D_3_POSTGRESQL_REGRESSION_REPORT.md`
  - `docs/quality/PHASE_4E_DEPLOYMENT_READINESS_REPORT.md`
  - `frontend/Dockerfile.prod`
  - `frontend/nginx.prod.conf`
  - `scripts/backup/` (`backup-postgres.sh`, `restore-postgres.sh`, `retention.py`, `backup-status.sh`, `cable-manager-backup.service`, `cable-manager-backup.timer`)

*Classification: Verified by actual execution (`git status --short`).*

---

## 3. Docker Port & Network Security Audit

A thorough structural audit of `docker-compose.prod.yml` was executed via `docker compose config`:

| Service | Image / Build Context | Network Membership | Published Host Ports | Internal Container Ports | Host Reachability | Security Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`db`** | `postgres:16-alpine` | `cable-prod-net` (`172.28.0.0/24`) | **NONE** | 5432/tcp | Completely inaccessible from host or external networks | **SAFE / SECURE** |
| **`backend`** | `backend/Dockerfile.prod` | `cable-prod-net` (`172.28.0.0/24`) | **NONE** | 8000/tcp | Accessible only to Nginx via Docker internal bridge | **SAFE / SECURE** |
| **`frontend`** | `frontend/Dockerfile.prod` | `cable-prod-net` (`172.28.0.10`) | `127.0.0.1:8080:8080` (or `${BIND_IP}:${PROD_PORT}:8080`) | 8080/tcp | Accessible on host loopback; reverse-proxies to backend:8000 | **SAFE / SECURE** |

### Specific Checks:
- **No Wildcard Binding in Baseline:** `BIND_IP` defaults to `127.0.0.1`. When unset, Docker publishes exclusively to loopback, avoiding accidental `0.0.0.0` exposure.
- **No Development Port Inheritance:** Verified that development ports (`5173`, `5432`) are completely absent from `docker-compose.prod.yml`.
- **DNS Isolation:** All inter-service traffic uses Docker's internal embedded DNS server (`127.0.0.11`) to resolve `db` and `backend`.

*Classification: Verified by actual execution (`docker compose -f docker-compose.prod.yml config`).*

---

## 4. UFW and Docker Firewall Interaction Audit

### The Linux Kernel Networking Reality:
On Linux systems, UFW manages packet filtering rules primarily within the `INPUT` chain of the `filter` table:
```text
Packets Arriving at NIC -> raw (PREROUTING) -> nat (PREROUTING) -> mangle (PREROUTING)
                                                                   |
                    [Packet Destination = Host Local Process?] ----+
                                 |                                 |
                                YES                               NO (Container / Bridge)
                                 |                                 |
                           filter (INPUT)                    filter (FORWARD)
                                 |                                 |
                           UFW Rules Apply                  Docker Rules Apply (UFW Bypassed!)
```

1. **Why UFW Rules Fail Against Docker:**  
   Docker automatically installs network address translation (DNAT) rules in the `PREROUTING` chain. Traffic destined for a container port is rewritten to the container's private bridge IP (`172.28.0.x`) and routed directly to the `FORWARD` chain, completely bypassing UFW's `INPUT` chain.
2. **Consequence of Earlier Documentation:**  
   The earlier draft in Phase 4E suggested that running `sudo ufw allow from 192.168.1.0/24 to any port 8080` was sufficient to protect the application on a local LAN. In reality, on a standard Ubuntu host with Docker active, a device outside that subnet could still reach the container if the port was published to all interfaces!
3. **Corrective Action Taken:**  
   - Updated `docs/deployment/NETWORK_AND_TLS_GUIDE.md`.
   - Replaced flawed UFW instructions with explicit interface binding (`BIND_IP=192.168.1.100`) and the mandatory `DOCKER-USER` iptables chain filtering rule:
     ```bash
     sudo iptables -I DOCKER-USER -i eth0 -p tcp --dport 8080 ! -s 192.168.1.0/24 -j DROP
     ```

*Classification: Verified by source inspection & Linux network architecture analysis.*

---

## 5. Deployment Modes Evaluation & Verdicts

### Mode A: Localhost-Only Deployment
- **Status:** **APPROVED FOR PRODUCTION**
- **Properties:**
  - Binds to `127.0.0.1:8080`.
  - Zero external attack surface.
  - No firewall interaction issues.
  - Zero possibility of wireless packet sniffing.
  - Ideal for single-operator mini-PC or shop desktop counter terminal.

### Mode B: Private Shop Wi-Fi / LAN Deployment
- **Status:** **NOT APPROVED IN CURRENT BASELINE (Requires Manual TLS & Firewall Setup)**
- **Requirements Before Approval:**
  1. Mandatory HTTPS termination (plain HTTP over wireless airwaves is rejected).
  2. Static IP reservation on the shop router for the server host.
  3. Strict `BIND_IP` binding to the specific LAN interface.
  4. `DOCKER-USER` chain iptables rule configured.

### Mode C: Remote Access
- **Status:** **DEFERRED (Not Implemented / Optional)**
- **Requirements Before Approval:**
  - Strict rejection of router port-forwarding and public VPS reverse proxies.
  - Only approved via private end-to-end encrypted mesh VPNs (WireGuard or Tailscale).

---

## 6. TLS & Reverse Proxy Configuration Audit

- **Current Implementation:** Nginx reverse proxy listens strictly on plain HTTP (`listen 8080;` in `frontend/nginx.prod.conf`).
- **Claim Verification:** Previous Phase 4E report accurately marked HTTPS as "Not pre-configured; templates provided".
- **Reverse Proxy Header Security:**
  - `X-Forwarded-For`, `X-Real-IP`, `X-Forwarded-Proto`, and `Host` headers are forwarded by Nginx.
  - In `backend/Dockerfile.prod`, `uvicorn` runs with:
    ```bash
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips "${TRUSTED_PROXIES:-127.0.0.1}"
    ```
  - In `docker-compose.prod.yml`, `TRUSTED_PROXIES` is set to `127.0.0.1,172.28.0.10`.
  - Backend rate limiter strictly rejects client IPs claiming to originate from untrusted reverse proxies.

*Classification: Verified by source inspection (`frontend/nginx.prod.conf`, `backend/Dockerfile.prod`).*

---

## 7. Installation Command Accuracy & Source Verification

Every operational command documented in `docs/deployment/PRODUCTION_INSTALLATION_GUIDE.md` and related runbooks was cross-referenced with actual source files:

| Documented Command | Target Source File | Parameters Checked | Verification Outcome |
| :--- | :--- | :--- | :--- |
| `docker compose -f docker-compose.prod.yml up -d db` | `docker-compose.prod.yml` | Service name `db` | **ACCURATE** |
| `docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head` | `backend/alembic.ini`, `backend/Dockerfile.prod` | Working directory `/app`, service `backend` | **ACCURATE** |
| `docker compose -f docker-compose.prod.yml run --rm backend python -m app.cli reset-admin-password --email <email>` | `backend/app/cli.py` | Argument `--email`, subcommand `reset-admin-password` | **ACCURATE** |
| `curl -i http://127.0.0.1:8080/health` | `frontend/nginx.prod.conf`, `backend/app/main.py` | Nginx location `/health` -> `backend:8000/health` | **ACCURATE** |
| `scripts/backup/backup-status.sh` | `scripts/backup/backup-status.sh` | Executable permissions, exit codes | **ACCURATE** |
| `scripts/backup/backup-postgres.sh` | `scripts/backup/backup-postgres.sh` | Preflight checks, GPG encryption stream | **ACCURATE** |
| `scripts/backup/restore-postgres.sh --backup-file <f> --target-db <d> --gpg-key <k>` | `scripts/backup/restore-postgres.sh` | CLI argument parsing, manifest SHA-256 check | **ACCURATE** |
| `systemd-analyze verify ...` | `scripts/backup/cable-manager-backup.service` | Sandboxing directives, unit syntax | **ACCURATE** |

*Classification: Verified by source inspection & unit test validation.*

---

## 8. Backup Deployment Privileges Re-Evaluation

The audit confirmed the exact operational security boundaries of the automated backup service:
1. **Root-Equivalence of Docker Socket:**  
   The scheduled backup service mounts `/run/docker.sock` to run `pg_dump` inside the database container. As established in Phase 4D.2, write access to `/run/docker.sock` is root-equivalent on Linux.
2. **Defense-in-Depth Measures:**  
   The service does not grant general network access, denies setuid escalation (`NoNewPrivileges=true`, `RestrictSUIDSGID=true`), restricts umask (`UMask=0077`), and isolates filesystem namespaces (`ProtectSystem=strict`, `ProtectHome=read-only`).
3. **Keyring Separation:**  
   The service reads public keys from `/etc/cable-manager/gnupg` (`BACKUP_GNUPGHOME`). The private recovery key is **never** installed on the host.

---

## 9. Findings Classified by Severity

### Finding 1 (High Severity - Corrected): Ineffective UFW Firewall Guidance for Docker
- **Issue:** Suggesting standard UFW allow/deny rules for Docker-published ports gave operators a false sense of security due to the Docker iptables bypass.
- **Correction:** Updated `docs/deployment/NETWORK_AND_TLS_GUIDE.md` to mandate explicit interface binding (`BIND_IP`) and document `DOCKER-USER` chain filtering rules.

### Finding 2 (High Severity - Corrected): Insecure Plain HTTP over Shop LAN
- **Issue:** Mode B deployment draft permitted plain HTTP access on local shop Wi-Fi.
- **Correction:** Mode B is now formally marked as **NOT APPROVED** without manual HTTPS termination. Updated documentation to mandate TLS termination before opening access to shop wireless networks.

### Finding 3 (Medium Severity - Reconciled): Docker Socket Privilege Transparency
- **Issue:** Operators might assume systemd sandboxing eliminates the container breakout risk of `/run/docker.sock`.
- **Correction:** Documented transparently in all backup and deployment guides that Docker socket access remains root-equivalent.

---

## 10. Verification Matrix

| Audit Item | Verification Status | Basis / Evidence |
| :--- | :--- | :--- |
| Compose network isolation & zero DB port exposure | **Verified by actual execution** | `docker compose -f docker-compose.prod.yml config` confirmed 0 published ports on `db` and `backend`. |
| Compose syntax with dummy environment | **Verified by actual execution** | Executed `docker compose config` with dummy values; clean exit code 0. |
| CLI command syntax & argument names | **Verified by source inspection** | Inspected `app/cli.py`, `app/routes/auth.py`, `backend/Dockerfile.prod`. |
| Nginx reverse proxy configuration & headers | **Verified by source inspection** | Inspected `frontend/nginx.prod.conf`; verified proxy headers and security headers. |
| Systemd syntax & parameter validity | **Verified by actual execution** | `systemd-analyze verify` passed with 0 errors and 0 warnings. |
| Zero persistent database contamination | **Verified by actual execution** | Port 5432 was never contacted or bound. |
| Systemd timer inactivity | **Verified by actual execution** | `systemctl is-active/is-enabled` reported `inactive` / `not-found`. |
| Host firewall rule enforcement (`DOCKER-USER`) | **Pending physical deployment** | Rule must be applied on the physical Linux production host machine during installation. |
| Physical GPG key offline custody | **Pending physical deployment** | Operator must physically store private key USB drive in business safe. |

---

## 11. Conclusion & Stop Gate Notice

The deployment security audit is complete. All identified risks regarding Docker firewall interactions and LAN HTTP exposure have been corrected in documentation. Cable Data Manager is confirmed to be securely deployable in **Mode A (Localhost Only)** out-of-the-box, with a clear, secure path for future LAN and remote access.

**Safety Barrier Enforced:**  
No production containers have been started. No host firewall rules were modified. No systemd timers or services were enabled. No Git commits were made. Awaiting explicit user approval.
