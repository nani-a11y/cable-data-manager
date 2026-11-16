# Cable Data Manager

**A modern, self-hosted customer register and payment management web application for independent local cable TV operators.**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![React 18](https://img.shields.io/badge/React-18.3-61dafb.svg)](https://react.dev/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Docker Compose](https://img.shields.io/badge/Docker-Compose_v2-2496ed.svg)](https://docs.docker.com/compose/)

---

## 1. Product Purpose & Philosophy

Independent local cable TV operators manage hundreds of residential subscribers, collecting monthly subscription fees via cash and UPI. Many operators still rely on paper registers or complex multi-tenant commercial SaaS products that charge monthly subscriptions, sell customer data, or stop working during broadband outages.

**Cable Data Manager** is built on different principles:
- **100% Free & Open Source:** Zero subscription fees, zero license keys, zero recurring costs.
- **Strict Data Privacy:** Zero external telemetry. Your customer records and payment history never leave your computer.
- **Offline Reliability:** Operates completely over local LAN or localhost without requiring an active internet connection.
- **Single-Operator Architecture:** One dedicated database per installation. No shared cloud databases or multi-tenant complexity.
- **Financial Precision:** Exact monetary calculations using PostgreSQL `Numeric(12, 2)` (never floating-point). Overpayment advance credits, chronological Khata passbooks, and audit-controlled payment reversals.

---

## 2. Key Features

### 📋 Customer Register
- Complete subscriber directory with search by name, phone, or STB (Set-Top Box) number.
- Filter by service area and payment status (**Paid**, **Partial**, **Unpaid**, **Advance**).
- Dual view: Responsive desktop data table and touch-optimized mobile customer cards (`< 700px`).
- Quick-action buttons: 1-click payment collection, instant Khata passbook view, customer edit, and deactivation.

### 💰 Financial Engine & Khata Passbook
- Exact decimal arithmetic for all balance and transaction calculations.
- Chronological customer passbook displaying opening balance, monthly invoices, cash/UPI receipts, payment reversals, and running net balances.
- Advance balance credit handling: excess payments are automatically credited forward toward future monthly invoices.
- Soft-delete audit logging: payment reversals require mandatory reason documentation and automatically recalculate customer balances.

### 📅 Billing Cycle Automation
- Automated monthly invoice generation for all active subscribers based on their assigned monthly package rate.
- Duplicate prevention: idempotent billing engine guarantees zero accidental double-billing within the same billing cycle.
- Grace period tracking and overdue balance calculations.

### 📍 Service Areas & Business Customization
- Configurable service delivery zones with active subscriber counts.
- Business profile settings: operator business name, contact phone, street address, currency, and default monthly subscription rate.

### 🔒 Enterprise-Grade Security
- Password hashing using modern **Argon2id** (`t=3, m=65536, p=4`).
- Strict production password policy: minimum 12 characters, entropy requirements, common dictionary attack rejection.
- In-memory sliding-window IP rate limiting on login endpoints to defeat automated brute-force attacks.
- Non-root unprivileged Docker containers (`appuser:10001` for backend, `nginx:101` for frontend).
- Security HTTP headers: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, and restrictive `Content-Security-Policy`.

---

## 3. Technology Stack

| Layer | Technology | Version | Purpose |
|---|---|---|---|
| **Frontend** | React, TypeScript, Vite, Tailwind CSS | 18.3 / 6.0 | Single-Page Application (SPA) with responsive mobile UI |
| **Fonts** | `@fontsource/dm-sans`, `@fontsource/manrope` | Latest | 100% self-hosted, offline WOFF2 typography |
| **Backend API** | Python, FastAPI, Pydantic v2 | 3.12 / 0.115 | High-performance asynchronous REST API |
| **Database** | PostgreSQL | 16 | ACID-compliant relational storage with `Numeric(12, 2)` precision |
| **Migrations** | Alembic | 1.14 | Version-controlled schema migrations (0001 → 0002 → 0003) |
| **Reverse Proxy** | Nginx Alpine | 1.27 | Hardened HTTP reverse proxy and static asset server |
| **Packaging** | Docker & Docker Compose | v2 | Containerized, reproducible production deployment |
| **Backup** | Bash, GNU pg_dump, GnuPG 2 | Latest | Streaming encrypted backups to external USB storage |

---

## 4. Architecture & Data Isolation

```text
+-------------------------------------------------------------------------+
| Local Computer / Server (Host Machine)                                  |
|                                                                         |
|  Browser (Localhost or LAN)                                             |
|        |                                                                |
|        | HTTP Port 8080 (127.0.0.1 or LAN IP)                           |
|        v                                                                |
|  +-------------------------------------------------------------------+  |
|  | Nginx Container (:8080)                                           |  |
|  | - Serves React Static Bundle & Self-Hosted Fonts                  |  |
|  | - Proxies /api/* to FastAPI backend                               |  |
|  | - Security Headers, Caching, and Request Buffering                |  |
|  +---------------------------------+---------------------------------+  |
|                                    | (Isolated Docker Network)          |
|                                    v                                    |
|                 +------------------------------------+                  |
|                 | FastAPI Backend Container (:8000)  |                  |
|                 | - Lifespan DB Connection & Seeding |                  |
|                 | - Argon2id & Rate Limiting Engine  |                  |
|                 | - Financial Engine & Business APIs |                  |
|                 +------------------+-----------------+                  |
|                                    | (Internal DB Port Only)            |
|                                    v                                    |
|                 +------------------------------------+                  |
|                 | PostgreSQL 16 Database (:5432)     |                  |
|                 | - Numeric(12, 2) Ledger Tables     |                  |
|                 | - Unexposed to Host Network        |                  |
|                 +------------------+-----------------+                  |
|                                    |                                    |
|                                    v (Encrypted Pipe: pg_dump | gpg)    |
|                 +------------------------------------+                  |
|                 | External USB Storage: /mnt/...     |                  |
|                 +------------------------------------+                  |
+-------------------------------------------------------------------------+
```

- **No Public Cloud:** All services run locally inside isolated Docker containers.
- **Zero Telemetry:** The application makes **zero outbound requests** to external servers.
- **Port Isolation:** PostgreSQL (port 5432) and FastAPI (port 8000) are never exposed to the host network. Only Nginx is accessible on the configured host interface (`BIND_IP:8080`).

---

## 5. Installation & Deployment

We support two installation approaches:

### Approach A: Production Docker Compose (Verified & Recommended)

This approach uses standard Docker Compose and requires only basic terminal familiarity.

#### Prerequisites
- Operating System: Ubuntu Server/Desktop 22.04/24.04 LTS or Debian 12 (recommended).
- Docker Engine & Docker Compose v2 installed.
- 4 GB RAM minimum (8 GB recommended).
- Dedicated external USB drive (for encrypted backups).

#### Step 1: Clone the Repository
```bash
git clone https://github.com/your-username/cable-manager.git /opt/cable-manager
cd /opt/cable-manager
```

#### Step 2: Configure Environment Variables
Copy the template and set file permissions:
```bash
cp .env.example .env
chmod 0600 .env
```

Edit `.env` using your preferred editor (`nano .env`):
1. Set a strong database password:
   ```bash
   openssl rand -hex 24
   ```
2. Generate a 256-bit JWT secret (minimum 32 characters required in production):
   ```bash
   openssl rand -hex 32
   ```
3. Set your initial administrator login email and password (`ADMIN_EMAIL` and `ADMIN_PASSWORD`).
4. Set `APP_ENV=production`.

#### Step 3: Initialize Database & Run Migrations
Start the database service and execute Alembic migrations:
```bash
# Start PostgreSQL database container
docker compose -f docker-compose.prod.yml up -d db

# Apply database migrations to head revision
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head
```

#### Step 4: Launch the Application
```bash
docker compose -f docker-compose.prod.yml up -d
```

Verify that all three services report healthy:
```bash
docker compose -f docker-compose.prod.yml ps
```

Open your browser to:
```text
http://localhost:8080
```

---

### Approach B: Guided Interactive Installer (`scripts/install.sh`) [Planned]

> [!NOTE]
> **Status: Planned / In Roadmap for Release v1.1.**<br/>
> An automated, menu-driven bash installer script (`scripts/install.sh`) is currently planned to automate Docker prerequisite checks, `.env` secret generation, GPG backup key creation, and systemd service registration in a single interactive terminal walkthrough. Until Release v1.1 is tagged, operators should use **Approach A (Production Docker Compose)** above.

---

## 6. Daily Operating Instructions

1. **Log In:** Open `http://localhost:8080`, enter your configured administrator email and password, and click **Sign in**.
2. **Configure Business:** Navigate to **Settings** and enter your business name, contact phone, operating address, and default monthly subscription rate (e.g. ₹300).
3. **Add Service Areas:** Navigate to **Service Areas** and create delivery zones (e.g. "Main Market", "Sector 4").
4. **Register Customers:** In **Collection Register**, click **New Customer**, fill in their name, phone, set-top box number, and assigned service area.
5. **Collect Payments:** On any customer row, click **Collect**, enter the cash or UPI amount received, select the payment mode, and submit. The passbook balance updates instantly.
6. **Generate Monthly Invoices:** On the 1st of each month, navigate to **Billing Management** and click **Generate Monthly Invoices**. Invoices are created for all active subscribers with zero duplicate billing.

---

## 7. Password Recovery CLI

If the administrator password is forgotten, it can be reset directly from the host terminal without plaintext logging:

```bash
docker compose -f docker-compose.prod.yml run --rm backend python -m app.cli reset-admin-password --email your-email@example.com
```

The CLI prompts interactively with masked input and enforces the production password policy ($\ge 12$ characters, entropy, dictionary check).

---

## 8. Backup & Disaster Recovery

Nightly backups are automated via systemd timer and GPG public-key stream encryption:
- Backups are written directly to `/mnt/cable-manager-backups` (dedicated external USB SSD).
- The public key on the server encrypts dumps during unattended nightly execution.
- The private decryption key is kept strictly offline by the business owner.
- To inspect backup status:
  ```bash
  bash scripts/backup/backup-status.sh
  ```
- Detailed setup instructions are documented in [`docs/deployment/BACKUP_OPERATIONS_GUIDE.md`](docs/deployment/BACKUP_OPERATIONS_GUIDE.md).

---

## 9. Development & Testing

To run the application locally in development mode:
```bash
# Backend virtual environment
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.lock

# Run pytest regression suite
pytest tests -v

# Frontend development server
cd ../frontend
npm ci
npm run dev
```

---

## 10. Project Structure

```text
├── backend/
│   ├── alembic/                # Database migrations (0001, 0002, 0003)
│   ├── app/                    # FastAPI application, routes, models, and services
│   │   ├── cli.py              # Administration CLI (password reset)
│   │   ├── config.py           # Production environment validation
│   │   ├── models.py           # SQLAlchemy 2.0 database models
│   │   ├── rate_limiter.py     # Login brute-force rate limiter
│   │   ├── security.py         # Argon2id hashing and password policies
│   │   └── routes/             # Auth, customers, billing, payments, settings
│   ├── tests/                  # Pytest test suite (100 collected test cases)
│   ├── Dockerfile.prod         # Unprivileged Python 3.12 production container
│   └── requirements*.lock      # Cryptographically locked dependencies with SHA-256 hashes
├── frontend/
│   ├── src/                    # React components, views, styles, and API client
│   │   ├── App.tsx             # Main routing and navigation shell
│   │   ├── CustomersView.tsx   # Collection register (desktop table & mobile cards)
│   │   ├── BillingView.tsx     # Monthly invoice cycle manager
│   │   ├── ReportsView.tsx     # Monthly collection register and revenue reports
│   │   ├── PaymentsView.tsx    # Receipt log and audit reversals
│   │   ├── AreasView.tsx       # Service area management
│   │   └── BusinessSetup.tsx   # Operator profile and billing parameters
│   ├── public/                 # Static favicon and branding assets
│   ├── Dockerfile.prod         # Multi-stage Node build with Nginx reverse proxy
│   └── nginx.prod.conf         # Hardened Nginx production configuration
├── docs/
│   ├── architecture/           # System, database, and security specifications
│   ├── deployment/             # Step-by-step production installation runbooks
│   └── quality/                # Sprint verification and audit reports
├── scripts/
│   ├── backup/                 # GPG backup, restore, retention, and systemd units
│   └── health-check.sh         # Deployment verification scripts
├── docker-compose.prod.yml     # Hardened production Compose configuration
└── docker-compose.yml          # Local development Compose configuration
```

---

## 11. Contributing

Contributions are welcome! Please open an issue to discuss proposed changes before submitting pull requests. All submissions must pass automated pytest regression tests and `git diff --check`.

---

## 12. License

This project is open-source software licensed under the terms of the [MIT License](LICENSE).
