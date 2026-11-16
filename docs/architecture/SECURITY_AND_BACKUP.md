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

## Backup, Restore & Disaster Recovery Architecture (Phase 4C Implemented)

### 1. Architecture Overview
- **Backup Utility:** `scripts/backup/backup-postgres.sh`
- **Restore Utility:** `scripts/backup/restore-postgres.sh`
- **Retention Manager:** `scripts/backup/retention.py`
- **Status & Monitoring:** `scripts/backup/backup-status.sh`
- **Systemd Units:** `scripts/backup/cable-manager-backup.service` & `cable-manager-backup.timer`
- **Dump Format:** PostgreSQL 16 custom format (`pg_dump -Fc`), compressed, with table of contents, sequences, indexes, and constraints.
- **Encryption:** Asymmetric GPG public-key stream encryption (`gpg --encrypt --recipient`).
- **Target Destination:** Configurable dedicated external SSD mount (default `/mnt/cable-manager-backups`).

#### 1.1 Checksum Integrity vs. Cryptographic Authenticity
- **Checksum Role:** The SHA-256 checksum recorded in the `.manifest` file detects accidental corruption, truncated dumps, bit rot, and storage faults.
- **Important Distinction:** A plaintext SHA-256 manifest does **NOT** provide cryptographic authenticity against an active adversary with root or filesystem access, because an attacker could modify both the dump and the manifest.
- **Confidentiality & Verification:** GPG public-key encryption provides data confidentiality on the backup disk. Archive structure and table-of-contents validation are performed during restoration via `pg_restore --list`. True digital signature authentication would require an offline operator signing key; storing a private signing key on an automated production server is intentionally avoided to prevent key compromise.

### 2. Encryption & Key Management Procedure
- **Principle of Least Privilege:** The production server requires **only the GPG public key** to perform unattended daily backups. The private decryption key is **never stored** on the production server.
- **Operator Keypair Generation (Execute on Secure Admin Machine):**
  ```bash
  gpg --batch --generate-key <<EOF
  Key-Type: RSA
  Key-Length: 4096
  Subkey-Type: RSA
  Subkey-Length: 4096
  Name-Real: Cable Data Manager Backup Key
  Name-Email: backup@cable-manager.local
  Expire-Date: 0
  Passphrase: <STRONG_OFFLINE_OPERATOR_PASSPHRASE>
  %commit
  EOF
  ```
- **Exporting Public Key to Production Host:**
  ```bash
  gpg --armor --export backup@cable-manager.local > backup-public-key.asc
  # Transfer backup-public-key.asc to production server
  gpg --import backup-public-key.asc
  ```
- **Safeguarding Private Recovery Key:**
  1. Export private key to offline password-protected USB flash drive:
     `gpg --armor --export-secret-keys backup@cable-manager.local > cable-manager-recovery.key`
  2. Store two physical copies in separate secure physical locations (e.g. office fireproof safe and home lockbox).
  3. **WARNING:** Losing the private key makes encrypted backups completely unrecoverable. Never lose the private key or its passphrase.

### 3. External SSD Preparation & Mount Configuration
1. Identify external drive: `lsblk -f`
2. Format external SSD with ext4 filesystem:
   `sudo mkfs.ext4 -L CABLE_BACKUPS /dev/sdX1`
3. Create mountpoint with restricted permissions:
   `sudo mkdir -p /mnt/cable-manager-backups && sudo chmod 0700 /mnt/cable-manager-backups`
4. Add to `/etc/fstab` using UUID for resilient boot mounting:
   `UUID=<DRIVE_UUID> /mnt/cable-manager-backups ext4 noatime,nodev,nosuid 0 2`
5. Test mount: `sudo mount -a`
6. Set `REQUIRE_MOUNT=true` in `.env`. If the SSD is disconnected, `backup-postgres.sh` will immediately abort with exit code 3, preventing accidental fills of the host root filesystem.

### 4. Retention Policy & Pruning
- **Daily:** Retains 1 backup per day for the last 14 distinct days.
- **Weekly:** Retains 1 backup per week for the last 8 distinct calendar weeks.
- **Monthly:** Retains 1 backup per month for the last 12 distinct calendar months.
- **Safety Invariants:**
  1. The newest verified backup is ALWAYS retained regardless of age.
  2. Unverified or missing-manifest backups are never deleted automatically.
  3. Pruning never deletes all backups.
  4. Pruning executes only after a fresh backup has succeeded and has been verified with a valid manifest.

### 5. Automated Scheduling via Systemd
To install the daily timer on the production Linux PC:
```bash
sudo cp scripts/backup/cable-manager-backup.service /etc/systemd/system/
sudo cp scripts/backup/cable-manager-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cable-manager-backup.timer
```
- **Execution Schedule:** Daily at 02:00 local system time with `Persistent=true` (guarantees a missed backup runs immediately if PC was off).
- **Inspection:** Check status with `systemctl list-timers cable-manager-backup.timer` and `journalctl -u cable-manager-backup.service`.

### 6. Full Disaster Recovery Runbook (Host or Disk Failure)
In the event of total computer hardware destruction or disk failure:

1. **Procure Replacement Hardware:**
   - Any x86_64 or ARM64 PC running Debian 12 / Ubuntu 22.04+ LTS.
2. **Install Core Runtime:**
   - Install Docker Engine & Docker Compose plugin.
3. **Deploy Codebase & Secrets:**
   - Clone repository to `/opt/cable-manager` or restore project directory.
   - Recreate `.env` using operator's securely documented database password and JWT secret.
4. **Attach Backup Storage & Import Private Key:**
   - Connect the external backup SSD to the replacement machine.
   - Import the offline recovery private key into the local GPG keyring:
     `gpg --import /media/usb/cable-manager-recovery.key`
5. **Start PostgreSQL Database Container:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d db
   ```
6. **Execute Restore Utility:**
   ```bash
   bash scripts/backup/restore-postgres.sh \
     --backup-file /mnt/cable-manager-backups/cable_backup_<LATEST>.dump.gpg \
     --target-db cable_manager \
     --force-production-restore-i-know-what-i-am-doing
   ```
   (Type `RESTORE PRODUCTION DATABASE` when prompted).
7. **Start Application Services:**
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```
8. **Verify Restored Application:**
   - Navigate to `http://127.0.0.1:8080/health` (verify `{"status":"ok","database":"connected"}`).
   - Log in and verify subscriber register, monthly dues, and passbook history.

### 7. Recovery Objectives & Operational Realities
- **Recovery Point Objective (RPO) Target:** < 24 hours.
  - *Operational Dependency:* RPO is a **target, not an unconditional guarantee**. Actual RPO depends on:
    1. Daily timer firing at 02:00 local time without persistent machine downtime.
    2. The external backup SSD being physically connected and mounted.
    3. Adequate storage space (`MIN_DISK_SPACE_MB`).
    4. Successful GPG encryption and database availability.
    5. Active operator monitoring via `backup-status.sh` to quickly remediate failures.
  - If a backup fails or the SSD is disconnected, RPO degrades until the issue is detected and resolved.
- **Recovery Time Objective (RTO):**
  - **Status:** **RTO has not yet been formally established for production database sizes.**
  - *Measured Baseline:* During automated testing with a synthetic fixture (2 customers, sample transactions), decryption, checksum check, and schema restore executed in ~3-5 seconds. However, realistic production datasets with years of transaction history, audit logs, and complex indexes will have significantly different I/O and CPU requirements.
  - **Repeatable Drill Procedure for Establishing Real RTO:**
    1. Record start time ($T_0$) when disaster recovery begins.
    2. Provision replacement OS and Docker runtime ($T_1$).
    3. Mount backup SSD and import operator GPG private key ($T_2$).
    4. Execute `restore-postgres.sh` and record completion time ($T_3$).
    5. Verify application health and record time ($T_4$).
    - *Database Restore Time:* $T_3 - T_2$.
    - *Full System Recovery Time:* $T_4 - T_0$.

### 8. Optional Future Offsite Backup Strategies (Task 4C.11)
- **Secondary External SSD:** Rotate two encrypted external SSDs weekly (one on-site connected to the machine, one stored in an off-site physical location).
- **Encrypted Local Cloud Sync:** Operator-controlled, end-to-end encrypted file synchronization (e.g. `rclone` or encrypted BorgBackup) pushing `.dump.gpg` and `.manifest` artifacts to an offsite destination.
- *Notice:* No third-party cloud accounts, AWS S3, or Google Drive integrations are enabled in this phase to maintain 100% data sovereignty.

## Remaining risks and decisions

Owner must select gateway/identity provider, MFA/recovery policy, data residency
expectations, budget, RPO/RTO, retention, who can access backups, and incident
contacts. Public deployment is blocked until these controls and a restore drill
are accepted.
