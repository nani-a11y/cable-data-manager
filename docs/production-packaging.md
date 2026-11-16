# Production Packaging & Security Hardening (Phase 4B)

This document describes the production packaging, security controls, and operational tooling implemented for Cable Data Manager.

---

## 1. Development vs Production Differences

| Characteristic | Development (`docker-compose.yml`) | Production (`docker-compose.prod.yml`) |
| :--- | :--- | :--- |
| **Frontend Web Server** | Vite Development Server (`npm run dev`) | Static Nginx unprivileged reverse proxy (`nginxinc/nginx-unprivileged:alpine`) |
| **Frontend Port** | `127.0.0.1:5173` | Configurable `${BIND_IP:-127.0.0.1}:${PROD_PORT:-8080}` |
| **Backend Port** | Exposed on `127.0.0.1:8000` | **Unexposed to host**; accessible solely via reverse proxy `/api/` over internal Docker network |
| **Database Port** | Unexposed (accessible inside `cable-net`) | **Unexposed to host**; accessible solely inside `cable-prod-net` |
| **Database Volume** | `postgres_data` | `postgres_prod_data` (Isolated from dev data) |
| **Secret Validation** | Permissive (allows dev placeholders for quick testing) | **Strict**: Rejects known placeholders, empty values, secrets < 32 chars, low entropy, passwords < 12 chars, and wildcard proxies |
| **Container Users** | Root (standard development) | **Non-root**: backend runs as `appuser:appgroup` (UID 1000), frontend runs as `nginx` (UID 101) |
| **Log Rotation** | Docker default | Enforced: `max-size: 10m`, `max-file: 3` |
| **Schema Migrations** | `Base.metadata.create_all` automatically runs | **Manual/Automated Alembic upgrade**: Application startup never mutates schema silently |

---

## 2. Production Environment Variables

Before starting the production stack, create a secure `.env` file with genuine production values:

```bash
# Database Credentials
POSTGRES_DB=cable_manager
POSTGRES_USER=cable_admin
POSTGRES_PASSWORD=<STRONG_RANDOM_PASSWORD>
DATABASE_URL=postgresql+psycopg://cable_admin:<STRONG_RANDOM_PASSWORD>@db:5432/cable_manager

# Application Environment
APP_ENV=production

# JWT Configuration (Generate with: openssl rand -hex 32)
JWT_SECRET=<STRONG_CRYPTOGRAPHIC_RANDOM_SECRET_MIN_32_CHARS>
JWT_EXPIRE_MINUTES=1440

# Initial Admin Credentials (used only to seed the first admin if database is empty)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=<STRONG_INITIAL_ADMIN_PASSWORD_MIN_12_CHARS>

# Allowed CORS Origins (comma-separated)
CORS_ORIGINS=http://localhost:8080

# Trusted Proxies for Client IP Detection and Uvicorn Forwarded Headers
# Must be specific IPs or CIDR subnets (e.g. 172.16.0.0/12 for Docker bridge).
# Wildcard '*' is strictly rejected in production.
TRUSTED_PROXIES=127.0.0.1,172.16.0.0/12

# Host Binding & Port
# Defaults to 127.0.0.1 (loopback) for safety.
# In production with WireGuard or LAN, set BIND_IP to that specific interface IP:
# e.g., BIND_IP=10.8.0.1 or BIND_IP=192.168.1.100
BIND_IP=127.0.0.1
PROD_PORT=8080
```

---

## 3. Production Docker Compose Startup & Migrations

### Step 1: Validate Compose Configuration
```bash
docker compose -f docker-compose.prod.yml config
```

### Step 2: Build Production Images
```bash
docker compose -f docker-compose.prod.yml build
```

### Step 3: Run Database Migrations (Pre-requisite before starting application)
In production, schema changes are never silently applied at application startup. Execute Alembic migrations explicitly:
```bash
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

### Step 4: Launch Production Stack in Background
```bash
docker compose -f docker-compose.prod.yml up -d
```

### Step 5: Check Service Status and Health
```bash
docker compose -f docker-compose.prod.yml ps
```
All services (`db`, `backend`, `frontend`) must report `healthy`.

### Step 6: View Logs
```bash
docker compose -f docker-compose.prod.yml logs -f
```

---

## 4. Container Health Checks

Each production container includes automated health monitoring:

1. **Database (`db`)**:
   - Command: `pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}`
   - Interval: 10s, Timeout: 5s, Retries: 5, Start Period: 10s.
2. **Backend (`backend`)**:
   - Command: `python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8000/health")'`
   - Interval: 15s, Timeout: 5s, Retries: 3, Start Period: 15s.
   - Verifies both FastAPI process responsiveness and database connectivity via `SELECT 1`.
3. **Frontend (`frontend`)**:
   - Command: `wget -q --spider http://127.0.0.1:8080/health || exit 1`
   - Interval: 15s, Timeout: 5s, Retries: 3, Start Period: 10s.
   - Verifies Nginx availability and upstream proxying to backend health endpoint.

---

## 5. Security Controls

### 5.1 Production Secret & Credential Validation
When `APP_ENV=production`, the application validates at startup:
- `JWT_SECRET` must not be empty or a known placeholder (`insecure-default-jwt-secret-replace-in-env`, `secret`, `changeme`, etc.).
- `JWT_SECRET` must be at least 32 characters in length.
- `JWT_SECRET` must possess character diversity (minimum 8 distinct characters).
- `ADMIN_PASSWORD` must satisfy the strong password policy (minimum 12 characters, maximum 128 characters, not a weak default, minimum 4 distinct characters).
- `DATABASE_URL` must not use insecure default credentials (`cable_admin:password`).
- `TRUSTED_PROXIES` must not be empty, must not contain wildcard `*`, and must parse as valid IP/CIDR entities.

If validation fails, the process exits immediately with an actionable error without logging sensitive values.

### 5.2 Login Rate Limiting
Endpoint `/api/auth/login` enforces per-client-IP rate limiting:
- Tracks failed login attempts per client IP.
- After 5 consecutive failed attempts within a 60-second window, subsequent requests from that client IP are rejected with `HTTP 429 Too Many Requests`.
- The `429` response includes a `Retry-After` header indicating remaining lockout seconds.
- Successful authentication immediately clears any accumulated failure counts for that IP.
- Error messages on failure remain generic (`Invalid email or password`) to prevent account enumeration.

### 5.3 Trusted Proxy Client IP Resolution
To prevent header spoofing:
- Uvicorn is launched with `--proxy-headers --forwarded-allow-ips "${TRUSTED_PROXIES}"`. Wildcard `*` is forbidden.
- The rate limiter checks the direct network peer IP (`request.client.host`).
- Only if the peer IP belongs to an explicitly configured trusted proxy (`TRUSTED_PROXIES`, e.g. Docker bridge `172.16.0.0/12`) does it inspect `X-Forwarded-For` or `X-Real-IP`.
- Untrusted direct connections attempting to send spoofed `X-Forwarded-For` headers are evaluated strictly by their physical IP address.

---

## 6. Administrator Password Reset CLI

To safely reset an administrator password without external identity providers or email servers:

### Interactive Reset (Prompted securely via getpass):
```bash
# Inside running backend container:
docker compose -f docker-compose.prod.yml exec backend python -m app.cli reset-admin-password --email admin@example.com

# Or on host with virtual environment:
cd backend && .venv/bin/python -m app.cli reset-admin-password --email admin@example.com
```

### Safety Guarantees:
- **No Plaintext CLI Arguments:** Plaintext `--password` arguments are rejected by the parser to prevent leakage in shell history (`.bash_history`) and process tables (`ps aux`).
- Prompts for password entry and confirmation securely using `getpass` (no echo).
- Enforces strict password policy (12 to 128 characters, non-trivial, non-default).
- Connects using the configured application database (`DATABASE_URL`).
- Rejects requests if the specified administrator account does not exist (never creates spurious accounts).
- Hashes password using production Argon2id implementation.
- Never prints passwords or password hashes to stdout/stderr.
- Executes within an atomic database transaction with automatic rollback on error.

---

## 7. Automated Backups & Disaster Recovery (Phase 4C)

Cable Data Manager includes automated, encrypted backup and restore tooling to safeguard financial and customer records.

### 7.1 Key Utilities
- **Backup Script:** `scripts/backup/backup-postgres.sh`
- **Restore Utility:** `scripts/backup/restore-postgres.sh`
- **Retention Manager:** `scripts/backup/retention.py`
- **Monitoring & Status:** `scripts/backup/backup-status.sh`
- **Systemd Service/Timer:** `scripts/backup/cable-manager-backup.service` & `cable-manager-backup.timer`

### 7.2 Configuration Variables (.env)
```bash
# Backup Storage & Safety
BACKUP_DIR=/mnt/cable-manager-backups
REQUIRE_MOUNT=true
MIN_DISK_SPACE_MB=500

# GPG Public Key Recipient for Automated Encryption
BACKUP_GPG_RECIPIENT=backup@cable-manager.local

# Retention Policy Boundaries
DAILY_RETENTION=14
WEEKLY_RETENTION=8
MONTHLY_RETENTION=12
```

### 7.3 Operational Commands
- **Run Manual Backup:**
  ```bash
  bash scripts/backup/backup-postgres.sh
  ```
- **Check Backup Health & Checksum:**
  ```bash
  bash scripts/backup/backup-status.sh
  ```
- **Perform Test Restore Drill (Disposable DB):**
  ```bash
  bash scripts/backup/restore-postgres.sh \
    --backup-file /mnt/cable-manager-backups/cable_backup_<TIMESTAMP>.dump.gpg \
    --target-db cable_restore_test
  ```
- **Emergency Production Restore (Requires Explicit Confirmation):**
  ```bash
  bash scripts/backup/restore-postgres.sh \
    --backup-file /mnt/cable-manager-backups/cable_backup_<TIMESTAMP>.dump.gpg \
    --target-db cable_manager \
    --force-production-restore-i-know-what-i-am-doing
  ```
