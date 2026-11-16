# Production Installation & Deployment Runbook

**Project:** Cable Data Manager  
**Audience:** System Administrators & Technical Operators  
**Target Environment:** Local On-Premises Linux Host (Dedicated Mini-PC or Linux Desktop)  
**Security Profile:** Zero-Recurring Cost, Isolated Database, Encrypted Off-Host Backups

---

## 1. Hardware & Operating System Specifications

### 1.1 Minimum vs. Recommended Hardware Requirements

| Component | Minimum Specification | Recommended Specification | Rationale / Operator Notes |
| :--- | :--- | :--- | :--- |
| **Processor (CPU)** | 64-bit Dual-Core x86_64 (e.g. Intel Celeron J4125 / Core i3 4th gen) | Quad-Core x86_64 (e.g. Intel Core i3/i5 8th gen+, Ryzen 3/5, or Intel N100) | Fast Argon2id password hashing, snappy GPG stream compression, and rapid TypeScript/Python cold starts. |
| **System Memory (RAM)** | 4 GB DDR3/DDR4 | 8 GB DDR4+ | PostgreSQL 16 (~150MB), FastAPI/Uvicorn (~120MB), Nginx (~30MB), Docker overhead (~200MB), and Linux OS cache. |
| **Primary Storage (OS/App)**| 64 GB SATA SSD | 120 GB+ NVMe / SATA SSD | Fast database write-ahead log (WAL) synchronization and container image builds. Hard disk drives (HDDs) are discouraged. |
| **Backup Storage** | 32 GB Dedicated External USB 3.0 Drive / SSD | 128 GB+ Dedicated External USB 3.0 SSD | Partitioned with `ext4`; dedicated exclusively to GPG encrypted backups. |
| **Network Interface** | Single Gigabit Ethernet (1000BASE-T) or 802.11n Wi-Fi | Wired Gigabit Ethernet (Cat5e / Cat6) | Wired Ethernet guarantees low latency and avoids Wi-Fi packet drops during payment recording. |
| **Power Continuity (UPS)** | 600VA Line-Interactive UPS (e.g. APC / Microtek) | 600VA–1000VA UPS with USB battery signaling | **Mandatory.** Prevents filesystem/WAL corruption and ensures clean container shutdown during power outages. |

### 1.2 Supported Operating Systems
- **Recommended:** Ubuntu Server 22.04 LTS / 24.04 LTS (64-bit x86_64) or Debian 12 (Bookworm).
- **Desktop Alternatives:** Ubuntu Desktop 22.04/24.04, Linux Mint 21+, Debian 12 Desktop (if the operator uses the server directly as a point-of-sale terminal).
- **Windows PC Reuse:** Running Ubuntu Server inside Hyper-V or WSL2 is technically possible for testing, but **a native dual-boot or dedicated Linux installation is strongly recommended** for production to prevent Windows Update reboots from terminating the background server.

### 1.3 Host Dependencies
Install official Docker CE and Docker Compose v2 via the official Docker repository:
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin git gnupg python3
```

---

## 2. Directory Layout & Repository Setup

1. **Clone the Repository:**
   ```bash
   sudo mkdir -p /opt/cable-manager
   sudo chown $USER:$USER /opt/cable-manager
   git clone <repository_url> /opt/cable-manager
   cd /opt/cable-manager
   ```

2. **Verify Repository Baseline:**
   ```bash
   git status
   # Ensure HEAD matches the verified release commit
   ```

---

## 3. Cryptographic Secret Generation & Environment Configuration

The production stack strictly enforces high-entropy secrets and rejects insecure defaults (e.g., `CHANGE_THIS_DATABASE_PASSWORD` or `secret`).

1. **Create the Production `.env` File:**
   ```bash
   cp .env.example .env
   chmod 0600 .env
   ```

2. **Generate Cryptographic Secrets:**
   Execute the following commands on the deployment host to generate 256-bit random strings:
   ```bash
   # Generate PostgreSQL password
   openssl rand -hex 24

   # Generate JWT Secret (minimum 32 characters required)
   openssl rand -hex 32

   # Generate Temporary Initial Admin Password (or enter strong chosen password)
   openssl rand -base64 16
   ```

3. **Populate `.env`:**
   Configure the following parameters in `/opt/cable-manager/.env`:
   ```ini
   # Database Credentials
   POSTGRES_DB=cable_manager
   POSTGRES_USER=cable_admin
   POSTGRES_PASSWORD=<paste_generated_postgres_password>
   DATABASE_URL=postgresql+psycopg://cable_admin:<paste_generated_postgres_password>@db:5432/cable_manager

   # Application Environment
   APP_ENV=production

   # JWT Security
   JWT_SECRET=<paste_generated_jwt_secret>
   JWT_EXPIRE_MINUTES=1440

   # Initial Administrator Seed Credentials
   ADMIN_EMAIL=admin@cable-manager.local
   ADMIN_PASSWORD=<paste_generated_admin_password>

   # Allowed CORS Origins (set to match host access origin)
   # For Localhost Mode:
   CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
   # For Private LAN Mode (e.g., server IP 192.168.1.100):
   # CORS_ORIGINS=http://192.168.1.100:8080,http://localhost:8080,http://127.0.0.1:8080

   # Trusted Reverse Proxy Configuration
   # Frontend reverse proxy container has static IP 172.28.0.10 on cable-prod-net
   TRUSTED_PROXIES=127.0.0.1,172.28.0.10

   # Host Binding & Port
   # Mode A (Localhost only - default):
   BIND_IP=127.0.0.1
   # Mode B (Private LAN - replace with server LAN IP):
   # BIND_IP=192.168.1.100
   PROD_PORT=8080

   # Backup Configuration
   BACKUP_DIR=/mnt/cable-manager-backups
   REQUIRE_MOUNT=true
   MIN_DISK_SPACE_MB=500
   BACKUP_GPG_RECIPIENT=backup@cable-manager.local
   BACKUP_GNUPGHOME=/etc/cable-manager/gnupg
   ```

---

## 4. Production Build & Image Generation

Build production images locally from source:
```bash
docker compose -f docker-compose.prod.yml build
```
This builds:
1. `backend:latest` using `backend/Dockerfile.prod` (multi-stage Python 3.12-slim image running as unprivileged user `appuser:appgroup` UID 1000).
2. `frontend:latest` using `frontend/Dockerfile.prod` (multi-stage Node 20 build output served by unprivileged Nginx on port 8080).

---

## 5. Database Initialization & Alembic Migrations

1. **Start Only the PostgreSQL Database Service:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d db
   ```

2. **Wait for Database Health Check:**
   ```bash
   docker compose -f docker-compose.prod.yml ps db
   # Wait until STATUS displays "healthy"
   ```

3. **Execute Alembic Database Migrations:**
   Run the migration command via a transient backend container:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
   ```
   *Expected Output:*
   ```text
   INFO  [alembic.runtime.migration] Running upgrade  -> 0001_initial, initial migration
   INFO  [alembic.runtime.migration] Running upgrade 0001_initial -> 0002_business_settings, add business settings table
   INFO  [alembic.runtime.migration] Running upgrade 0002_business_settings -> 0003_customer_billing, add customers invoices payments allocations
   ```

---

## 6. Full Stack Launch & Health Verification

1. **Start the Entire Production Stack:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

2. **Verify Container Status:**
   ```bash
   docker compose -f docker-compose.prod.yml ps
   ```
   All 3 services (`db`, `backend`, `frontend`) must report `Up (healthy)`.

3. **Verify Health Endpoints:**
   ```bash
   # From host terminal:
   curl -i http://127.0.0.1:8080/health
   ```
   *Expected Response:*
   ```http
   HTTP/1.1 200 OK
   Content-Type: application/json

   {"status":"healthy","database":"connected"}
   ```

4. **Verify Frontend UI Loads:**
   Open a web browser on the host machine to `http://localhost:8080`. The login screen should display cleanly.

---

## 7. Initial Administrator Login & Password Setup

1. **First Login:**
   - URL: `http://localhost:8080`
   - Email: Value configured in `ADMIN_EMAIL` (e.g. `admin@cable-manager.local`)
   - Password: Value configured in `ADMIN_PASSWORD`

2. **Interactive Password Reset CLI (Recommended Procedure):**
   To change or recover an administrator password securely without storing it in `.env`:
   ```bash
   docker compose -f docker-compose.prod.yml run --rm backend python -m app.cli reset-admin-password --email admin@cable-manager.local
   ```
   The CLI prompts interactively with masked input:
   ```text
   Enter new admin password: 
   Confirm new admin password: 
   Success: Password for admin 'admin@cable-manager.local' has been successfully reset.
   ```
   *Note:* The password must be at least 12 characters long and pass the policy check (rejecting trivial sequential patterns like `123456` or `password`).

---

## 8. Post-Installation Verification Checklist

- [ ] PostgreSQL port 5432 is **NOT** exposed to host (`ss -tlpn | grep 5432` returns empty).
- [ ] Backend port 8000 is **NOT** exposed to host (`ss -tlpn | grep 8000` returns empty).
- [ ] Frontend port 8080 is bound strictly to configured `BIND_IP`.
- [ ] Health endpoint `/health` returns `200 OK` with database connected.
- [ ] Admin login succeeds; dashboard summary renders.
- [ ] `.env` file permissions are restricted to `chmod 0600`.
- [ ] Dedicated external SSD is partitioned and mounted at `/mnt/cable-manager-backups`.
