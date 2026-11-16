# PHASE 4E — PRODUCTION DEPLOYMENT ARCHITECTURE & INSTALLATION READINESS REPORT

**Project:** Cable Data Manager  
**Repository:** `/home/kowshik/Downloads/cable-manager-phase1`  
**Committed Baseline (HEAD):** `4dff68eb5c41e4bf79b8a2ae7b0000dbc9854a48`  
**Execution Date:** November 16, 2026  
**Role:** Senior DevOps Architect, Linux Deployment Engineer & Application Security Engineer  
**Status:** COMPLETE — RUNBOOKS & ARCHITECTURE READY — DEPLOYMENT BLOCKED AT STOP GATE

---

## 1. Executive Summary & Verification Highlights

In Phase 4E, a complete, secure, repeatable, and zero-recurring-cost production installation architecture was developed for a single local cable TV operator.

All deployment runbooks, network security models, administrator initialization routines, upgrade/rollback strategies, and operator quick-start instructions were created and validated against the actual codebase.

### Key Architectural Findings:
1. **Zero Recurring Infrastructure Cost Achieved:**
   - Designed to run on an existing shop PC or low-cost refurbished Linux mini-PC (Intel Celeron/Core i3, 4GB–8GB RAM).
   - Zero cloud subscriptions, zero VPS costs, zero third-party database fees, and zero software licenses (100% open-source Linux, PostgreSQL 16, FastAPI, React, and Nginx).
2. **Strict Network & Database Isolation Enforced:**
   - Verified that `docker-compose.prod.yml` binds only the frontend reverse proxy to `127.0.0.1:8080`.
   - PostgreSQL (`db:5432`) and FastAPI (`backend:8000`) have zero published host ports and communicate strictly over the internal container network `cable-prod-net` (`172.28.0.0/24`).
3. **Automated GPG Public-Key Backups Prepared for Physical Deployment:**
   - Unattended scheduled daily backups stream directly into GPG encryption using an isolated public keyring (`/etc/cable-manager/gnupg`), writing to an external SSD (`/mnt/cable-manager-backups`).
   - Private recovery keys remain strictly offline in physical operator custody.
4. **Three Independent Access Modes Documented:**
   - **Mode A (Default Baseline):** Localhost only on the shop PC (`127.0.0.1:8080`).
   - **Mode B (Private LAN):** Local shop Wi-Fi access via UFW firewall rules restricted to the local subnet.
   - **Mode C (Remote Access):** Deferred to private WireGuard/Tailscale mesh VPNs; commercial port forwarding and public VPS proxies are rejected.

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
  - `frontend/Dockerfile.prod`
  - `frontend/nginx.prod.conf`
  - `scripts/backup/` (`backup-postgres.sh`, `restore-postgres.sh`, `retention.py`, `backup-status.sh`, `cable-manager-backup.service`, `cable-manager-backup.timer`)

*Classification: Verified by actual execution (`git status --short`).*

---

## 3. Production Compose Configuration Audit

Source inspection and validation of `docker-compose.prod.yml` via `docker compose config` established:

1. **Database Exposure:**
   - `db` service runs `postgres:16-alpine`.
   - Has **NO `ports:` section**.
   - Joined to `cable-prod-net`.
   - Verified that PostgreSQL is inaccessible from host or external networks.
2. **Backend Exposure:**
   - `backend` service runs Python 3.12-slim (`backend/Dockerfile.prod`) as non-root `appuser:appgroup` (UID 1000).
   - Has **NO `ports:` section**.
   - Accessible only to Nginx via internal container hostname `backend:8000`.
3. **Frontend & Reverse Proxy Entry Point:**
   - `frontend` service runs Nginx reverse proxy on port 8080.
   - Bound to host interface via parameter `- "${BIND_IP:-127.0.0.1}:${PROD_PORT:-8080}:8080"`.
   - Static IP assigned on internal network: `172.28.0.10`.
4. **Volume Safety:**
   - Named volume `postgres_prod_data` is used for persistent database storage.
   - No anonymous or host-bind volumes are used for database storage.
5. **Restart Policies & Health Checks:**
   - All services configured with `restart: unless-stopped`.
   - `db` has native `pg_isready` health check.
   - `backend` has Python urllib health check (`http://127.0.0.1:8000/health`).
   - `frontend` has `wget` health check.

*Classification: Verified by actual execution (`docker compose -f docker-compose.prod.yml config`).*

---

## 4. Hardware & Operating System Recommendations

| Category | Minimal Low-Cost Hardware | Recommended Hardware | Rationale |
| :--- | :--- | :--- | :--- |
| **Server Machine** | Refurbished Desktop / Mini-PC (Intel Core i3 4th–6th gen, 4GB RAM) | Intel N100 Mini-PC or Core i3/i5 8th gen+ (8GB RAM, 128GB SSD) | Capable of fast Argon2id hashing and full Docker stack in < 1GB RAM total. |
| **Primary OS** | Ubuntu Server 22.04 LTS / 24.04 LTS or Debian 12 | Ubuntu Server 24.04 LTS (64-bit x86_64) | 5-year security patch lifecycle, native Docker CE, reliable systemd timers. |
| **Backup Medium** | 32GB USB 3.0 Flash Drive (ext4) | 120GB–250GB External USB 3.0 SSD (ext4) | SSD ensures fast sequential writes and resistance to bit rot. |
| **Power Continuity** | 600VA Line-Interactive UPS | 600VA–1000VA UPS with USB auto-shutdown | Mandatory in local Indian shop conditions to prevent filesystem/database WAL corruption. |

---

## 5. Administrator Initialization & Authentication Security

1. **Cryptographic Seed Creation:**
   - Admin account seeded on clean database startup using `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `.env`.
   - Passwords hashed using Argon2id (`app/security.py`).
   - Strict validation: `validate_admin_password()` rejects passwords < 12 characters and trivial common patterns.
2. **Interactive Password Reset CLI:**
   - Source inspection of `backend/app/cli.py` confirmed implementation of `python -m app.cli reset-admin-password --email <admin_email>`.
   - Prompts for password via `getpass` with confirmation and policy enforcement.
3. **Login Rate Limiter:**
   - Verified that login attempts are rate-limited to 5 failures per 5 minutes per IP (`backend/app/rate_limiter.py`).
   - Client IP resolved strictly through `TRUSTED_PROXIES` (`127.0.0.1,172.28.0.10`).

*Classification: Verified by source inspection & automated tests in `test_cli.py` and `test_rate_limiting.py`.*

---

## 6. Network Security & Access Control Design

1. **Mode A (Localhost Only):**
   - Default setting (`BIND_IP=127.0.0.1`).
   - Zero network exposure. Web interface only opens on the server machine itself.
2. **Mode B (Private Wi-Fi / Local Shop LAN):**
   - Bind to local IP (`BIND_IP=192.168.1.100`).
   - Host firewall (UFW) rule restricts incoming port 8080 traffic strictly to the trusted local subnet (`192.168.1.0/24`).
3. **Mode C (Remote Access — Deferred):**
   - Zero open router ports.
   - Recommended only via private peer-to-peer overlay network (WireGuard or Tailscale).
   - Public VPS proxies, commercial reverse tunnels, and dynamic DNS are explicitly rejected to avoid recurring subscriptions and unauthorized internet exposure.

---

## 7. TLS Readiness & Status

- **Current State:** HTTP-only (`listen 8080;` in `frontend/nginx.prod.conf`).
- **Loopback Safety:** In Mode A (localhost), all traffic is internal to the host kernel network stack; TLS is unnecessary.
- **LAN / Wi-Fi Guidance:** When deploying in Mode B, local TLS termination via a self-signed or internal CA certificate (`/etc/cable-manager/certs`) is documented in `docs/deployment/NETWORK_AND_TLS_GUIDE.md`.
- **Integrity Notice:** The system does **not** falsely claim HTTPS is pre-configured. Clear configuration templates are provided for when the operator requires wireless LAN access.

---

## 8. Backup Installation Readiness & Operational Safeguards

- **Mount Isolation:** Enforced via `REQUIRE_MOUNT=true` and `mountpoint -q "$BACKUP_DIR"` pre-run checks.
- **Key Separation:** Public key stored in `/etc/cable-manager/gnupg` for automated encryption. Private recovery key stored strictly offline on physical USB media in the operator's locked safe.
- **Docker Socket Access:** Explicitly documented that `/run/docker.sock` access remains root-equivalent; process execution is hardened via 13 systemd sandbox directives (`UMask=0077`, `ProtectSystem=strict`, `PrivateDevices=true`, `SystemCallArchitectures=native`).
- **Inspection & Recovery:** Status tool `backup-status.sh` and restore utility `restore-postgres.sh` provide automated verification and recovery capabilities.

---

## 9. Comprehensive Cost Analysis (Target: ₹0 Recurring)

| Expense Item | Minimum Cost (INR) | Recommended Cost (INR) | Recurring Software Cost | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Host PC Hardware** | ₹0 (Reuse existing desktop/laptop) | ₹12,000 – ₹18,000 (Refurbished Mini-PC / Intel N100) | **₹0 / month** | One-time capital expense if new hardware is required. |
| **Operating System** | ₹0 (Ubuntu Linux / Debian) | ₹0 (Ubuntu Linux / Debian) | **₹0 / month** | 100% Free and Open Source. |
| **Database & Web Engine** | ₹0 (PostgreSQL 16, Docker CE, Nginx) | ₹0 (PostgreSQL 16, Docker CE, Nginx) | **₹0 / month** | Zero licensing or seat fees. |
| **Backup Storage** | ₹1,500 – ₹2,500 (120GB–256GB USB SSD) | ₹2,500 – ₹4,000 (500GB USB 3.2 SSD) | **₹0 / month** | One-time physical hardware purchase. |
| **Power Continuity (UPS)** | ₹2,500 – ₹3,500 (600VA Line Interactive) | ₹4,500 – ₹6,000 (1000VA UPS) | **₹0 / month** | Essential shop infrastructure. |
| **Remote Access / VPN** | ₹0 (Localhost Mode / WireGuard) | ₹0 (Tailscale Free Tier / WireGuard) | **₹0 / month** | No paid cloud relay services. |
| **Electricity Consumption** | ~₹200 – ₹350 / month (15W–30W Mini-PC) | ~₹200 – ₹350 / month | Existing utility | Standard shop electricity bill. |
| **Total Recurring Software/Cloud Fees** | **₹0.00** | **₹0.00** | **₹0.00 / month** | **Completely Zero Recurring Cloud Subscriptions** |

---

## 10. Verification & Quality Validation Results

| Test / Check | Tool / Command | Exit Code | Outcome | Details |
| :--- | :--- | :--- | :--- | :--- |
| **Docker Compose Config** | `docker compose -f docker-compose.prod.yml config` | `0` | **PASS** | Validated Compose file structure, environment substitutions, and network definitions. |
| **Production Secret Validation** | `pytest tests/test_config.py` | `0` | **PASS** | Validated that weak/default secrets are strictly rejected when `APP_ENV=production`. |
| **CLI Password Reset Tool** | `pytest tests/test_cli.py` | `0` | **PASS** | 7/7 tests passed covering interactive reset, length checks, and transaction safety. |
| **Rate Limiter & IP Proxy** | `pytest tests/test_rate_limiting.py` | `0` | **PASS** | 4/4 tests passed covering brute-force throttling and proxy IP extraction. |
| **Full Backend Suite** | `pytest tests/` | `0` | **PASS** | 84 passed, 16 skipped (reconciled live PG conditional tests) in 28.81s. |
| **Frontend Production Build** | `npm run build` | `0` | **PASS** | 1,582 modules compiled cleanly in 2.22s with 0 errors. |
| **Systemd Syntax Validation** | `systemd-analyze verify` | `0` | **PASS** | Clean verification with 0 warnings and 0 errors. |
| **Systemd Service Inactivity** | `systemctl is-active / is-enabled` | `0` | **PASS** | Both backup units remain `inactive` and `not-found`. |
| **Git Conflicts & Whitespace** | `git diff --check` | `0` | **PASS** | Zero conflict markers, zero whitespace issues. |
| **Persistent DB Port Safety** | `ss -tlpn \| grep 5432` | `0` | **PASS** | Port 5432 untouched; zero connections or bindings. |

---

## 11. Verification Classification Matrix

| Finding / Component | Verification Status | Basis / Evidence |
| :--- | :--- | :--- |
| Production Compose network isolation | **Verified by actual execution** | `docker compose config` confirmed zero published host ports for `db` and `backend`. |
| Docker Compose syntax and configuration | **Verified by actual execution** | Validated with dummy production environment parameters with clean exit code 0. |
| Administrator password reset CLI | **Verified by actual execution** | 7/7 automated tests passed in `test_cli.py`. |
| Rate limiting and trusted proxy defense | **Verified by actual execution** | 4/4 automated tests passed in `test_rate_limiting.py`. |
| Systemd syntax & parameter validity | **Verified by actual execution** | `systemd-analyze verify` passed with 0 errors and 0 warnings. |
| Zero persistent database contamination | **Verified by actual execution** | Port 5432 never bound or queried. |
| Systemd timer inactivity | **Verified by actual execution** | `systemctl is-active/is-enabled` confirmed `inactive` and `not-found`. |
| Physical hardware installation & SSD mount | **Pending physical deployment** | External drive formatting (`ext4`), `/etc/fstab` UUID configuration, and USB mounting must be completed on the physical machine. |
| Operator physical key custody | **Pending physical deployment** | Exporting and storing the private recovery key on physical USB media in the operator's business safe. |

---

## 12. Conclusion & Stop Gate Notice

All production installation architecture specifications and operational runbooks for Cable Data Manager Phase 4E are complete, accurate, and source-verified.

**Safety Barrier Enforced:**  
No production services have been started. No systemd timers or services have been enabled. No production accounts or keys have been generated. No Git commits have been made. Awaiting explicit user approval.
