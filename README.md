# Cable Manager

Private, single-operator cable-business management application. This repository
contains the Phase 1 engineering foundation: safe Git baseline, reproducible locked dependencies,
Alembic migration baseline, automated pytest suite, and CI workflows.
The target product, architecture decisions, audit evidence, and roadmap are documented under
[`docs/`](docs/architecture/SYSTEM_ARCHITECTURE.md).

## Stack

- Frontend: React 18, TypeScript, Vite, Tailwind CSS (locked via `package-lock.json`)
- Backend: FastAPI, SQLAlchemy 2, Alembic (locked via `requirements.lock` with hashes)
- Database: PostgreSQL 16
- Local orchestration: Docker Compose
- Current authentication: app-level admin login with JWT and Argon2 (transitional)
- Current data model: `admin_users` table; no customer, invoice, or payment models exist yet

The app-level login is transitional behavior. The target architecture is one operator
authenticated at a private remote-access gateway; there are no customer accounts,
user registration, roles, or SaaS multi-tenancy. Do not remove the existing login until a
gateway replacement is implemented and verified in a separately approved application change.

## Local Setup

Prerequisites:
- Docker Engine and Docker Compose v2 (if using Docker socket on custom path, set `DOCKER_HOST` appropriately or unset if using default)
- Node.js 20+ (for host-side frontend build)
- Python 3.12+ (for local backend testing and migrations)

1. Preserve an existing `.env`. On first setup only, create it from the example:

   ```bash
   test -f .env || cp .env.example .env
   chmod 600 .env
   ```

2. Edit `.env` using a local editor; replace all `CHANGE_THIS_*` placeholders.
   Never paste or print its contents. Keep database passwords consistent
   between `POSTGRES_PASSWORD` and `DATABASE_URL`.

3. Run the safe preflight and validate Compose:

   ```bash
   bash scripts/preflight.sh
   bash scripts/validate-compose.sh
   ```

4. Start or rebuild the local stack:

   ```bash
   docker compose up --build -d
   bash scripts/health-check.sh
   ```

   Do not use `docker compose down -v` as it deletes the persistent database volume.

## Dependency Management

### Frontend

Locked using `package-lock.json` (npm lockfile v3).
To install dependencies reproducibly:

```bash
npm --prefix frontend ci
```

### Backend

Direct dependencies are declared in `backend/requirements.in` and `backend/requirements-dev.in`.
Locked dependencies with transitive packages and SHA-256 hashes are compiled in:
- `backend/requirements.lock` (application runtime)
- `backend/requirements-dev.lock` (development & testing runtime)

To install locked backend dependencies in an isolated virtual environment:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install --require-hashes -r backend/requirements-dev.lock
```

## Database Migrations (Alembic)

Database schema is managed via Alembic in `backend/alembic/`.

### Fresh Installations
On a fresh database without tables, apply all migrations to reach head:

```bash
cd backend
alembic upgrade head
```

### Existing Persistent Database (Preserving Account)
For an existing persistent database that already has the `admin_users` table created prior to Alembic introduction:
1. Verify database health: `bash scripts/health-check.sh`
2. Stamp the database to the baseline revision without running DDL:

   ```bash
   cd backend
   alembic stamp 0001_initial_admin_users
   ```

3. Verify parity: `alembic check` (reports "No new upgrade operations detected").

*CRITICAL:* Never run `drop_all`, reset, or destructive DDL against the persistent database volume.

## Testing & Validation

### Backend Tests (pytest)
Runs focused tests across health endpoints, database connectivity handling, configuration parsing, API authentication, and Alembic migrations against disposable test resources:

```bash
bash scripts/test-backend.sh
```

Or directly via pytest:
```bash
pytest backend/tests -v
```

### Frontend Typecheck & Build
Validates TypeScript compilation and Vite production build:

```bash
npm --prefix frontend run build
```

### Compose Validation
Validates compose configuration syntax and service bindings:

```bash
bash scripts/validate-compose.sh
```

## Git Workflow & Exclusions

A local Git repository is initialized on `main`.
Strict exclusions in `.gitignore` ensure:
- Secrets and environment files (`.env`, `*.key`, `*.pem`, `*.p12`) are excluded.
- Database volumes (`postgres_data/`, `*.db`, `*.sqlite`) are excluded.
- Customer data, exports, and backups (`*.csv`, `*.xlsx`, `*.bak`, `backups/`, `exports/`) are excluded.
- Build artifacts and dependencies (`node_modules/`, `dist/`, `.venv/`, `__pycache__/`, `*.tsbuildinfo`) are excluded.

## Continuous Integration (CI)

A minimal GitHub Actions workflow is located at `.github/workflows/ci.yml`. It runs on push and pull requests to `main`:
1. Sets up Python 3.12 and Node 20.
2. Installs locked backend dependencies with hash verification.
3. Executes backend pytest suite.
4. Installs frontend dependencies via `npm ci`.
5. Executes frontend typecheck and production build.
6. Validates Docker Compose configuration.

## Developer Shortcuts

VS Code tasks are located in `.vscode/tasks.json`. Safe scripts are in `scripts/`:

- `preflight.sh`: checks Docker availability, `.env` presence/permissions, placeholders, and Compose validity.
- `validate-compose.sh`: validates Compose configuration syntax.
- `compose-status.sh`: inspects status of running Compose services.
- `health-check.sh`: checks HTTP 200 on frontend and backend health endpoints.
- `check-dependencies.sh`: checks dependencies in running containers.
- `test-backend.sh`: executes the pytest test suite.

## Project Map

```text
backend/app/                 FastAPI application, configuration, and models
backend/alembic/             Alembic migrations and environment
backend/tests/               Backend automated test suite (pytest)
backend/requirements*.lock   Locked Python dependencies with SHA-256 hashes
frontend/src/                React UI, API client, and styles
frontend/package-lock.json   Locked npm dependencies
docs/                        Architecture, roadmap, security, and quality documents
scripts/                     Verification and test automation scripts
.github/workflows/ci.yml     GitHub Actions CI workflow
.vscode/tasks.json           Developer task entry points
docker-compose.yml           Local services configuration
```
