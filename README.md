# SLPHC 2026 Field Monitor Error Follow-up

A single-role Android tablet app for Field Monitors to log, track and follow up data-quality
errors that DQM communicates outside the system, a FastAPI server the tablets sync to, and a
web dashboard with reports for National DQM, Regional staff and District DQM.

Design doc: *SLPHC Field Monitor Error Follow-up — Android App Design* (Claude Doc).

```
server/      FastAPI + SQLAlchemy + PostgreSQL. Auth, sync, dashboard aggregates, reports, admin.
dashboard/   React 18 + Vite + Tailwind + Recharts. Dashboard, errors, monitors, teams, reports, admin.
android/     Kotlin + Jetpack Compose + Room (SQLCipher) + WorkManager. The tablet app.
```

## Run locally

Quickest: double-click `start-dev.bat`. It opens two windows (server on port 8000, dashboard on port 5173) and the browser at http://localhost:5173. Both stop when you close the windows or restart the PC; run it again afterwards.

Manually:

Server (SQLite by default, no Docker needed):

```bash
cd server
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows
.venv/Scripts/python -m scripts.seed_demo                                 # demo data
.venv/Scripts/uvicorn app.main:app --reload
```

Dashboard:

```bash
cd dashboard
npm install
npm run dev
```

Open http://localhost:5173. Demo logins (password `Password123`): `dqm.national`, `regional.western`,
`dqm.wau`; admin is `admin` / `change-me-immediately`. Field Monitor logins (`fm.wau`, `fm.war`,
`fm.bom`) are for the tablet app only.

Tests:

```bash
cd server && .venv/Scripts/python -m pytest
```

Or everything with Postgres in Docker: `cp .env.example .env` then `docker compose up`.

## Deploy to the VPS (Hostinger)

Source of truth is GitHub: https://github.com/tblaudfaust/SLDQMT . The VPS runs a clone of it under
`/opt/sldqmt` with Docker Compose (Postgres, API, dashboard, Caddy with automatic HTTPS, nightly backups).

First time, on a fresh Ubuntu 22.04/24.04 VPS, as root:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/tblaudfaust/SLDQMT/main/deploy/setup-vps.sh)
```

The script installs Docker, opens ports 22/80/443, clones the repository and creates `/opt/sldqmt/.env` with
random database and JWT secrets. Edit that file (set `DOMAIN` to the name whose DNS A record points at the VPS,
and `BOOTSTRAP_ADMIN_PASSWORD`), then run `bash /opt/sldqmt/deploy/update.sh`. Caddy obtains the TLS
certificate on first start. Sign in as admin, change the password, import the district supervisory-area files
(Reference lists page) and create the users.

Updating: push to `main`. The **Checks** workflow runs the server tests and the dashboard build; when it passes,
the **Deploy to VPS** workflow connects over SSH and runs `deploy/update.sh` (git pull, rebuild, restart, health
check). To enable it, add these repository secrets on GitHub (Settings → Secrets and variables → Actions):
`VPS_HOST`, `VPS_USER` (usually `root`), `VPS_SSH_KEY` (a private key whose public half is in the VPS
`~/.ssh/authorized_keys`), optional `VPS_PORT`. Manual alternative on the VPS: `bash /opt/sldqmt/deploy/update.sh`.

Tablet APK: the **Android APK** workflow builds `SLPHC-FieldMonitor-<ref>-<sha>.apk` on every change under
`android/` (download it from the workflow run's Artifacts) and attaches it to a GitHub Release when a tag such as
`v0.2.0` is pushed. Set the repository variable `API_BASE_URL` to `https://<your domain>/api/v1/` so the APK
talks to the VPS; add the `ANDROID_KEYSTORE_*` secrets to sign with a real key (see the workflow header).

## Tablet app

See `android/README.md`. Build locally with Android Studio, or download the APK built by the **Android APK**
GitHub Actions workflow (see Deploy above).

## Access rights and audit

Rights are `area.action` codes (see `server/app/core/permissions.py`). Each role has a default set that an administrator can change on the Roles and rights page; single users can be granted or denied individual rights. Geographic scope always applies on top. Records are soft-deleted with a reason and can be restored; every change is written to the audit log with the actor, time, address and field-level before/after values.

## API summary

| Path | Who | Purpose |
| --- | --- | --- |
| `POST /api/v1/auth/login`, `/auth/refresh`, `/auth/logout`, `GET /auth/me` | all | JWT auth |
| `POST /api/v1/devices/register` | tablet | Register a tablet |
| `POST /api/v1/sync/push`, `GET /sync/pull`, `GET /reference` | tablet | Sync |
| `GET /api/v1/dashboard/*`, `/errors`, `/errors/{id}` | web | Scoped aggregates and lists |
| `GET /api/v1/reports/{kind}?format=xlsx|pdf` | web | Reports |
| `/api/v1/dqm-reports`, `/dqm-reports/{id}/submit`, `/receive`, `/export`, `/dqm-reports/summary`, `/dqm-reports/analytics` | web | Annex A daily DQM report: district entry, national receipt, regional and national summaries, chart analytics |
| `/api/v1/exit-checkouts`, `/{id}/submit`, `/national-sign`, `/clearance`, `/export`, `/exit-checkouts/summary` | web | Field Exit Protocol check-outs: district certification, national countersign and clearance, summaries |
| `PATCH/DELETE /api/v1/errors/{id}`, `/errors/{id}/restore` | web (errors.edit / errors.delete) | Edit, soft-delete and restore error records from the dashboard |
| `/api/v1/admin/*` | by permission | Users, roles and rights (`/admin/roles`, `/admin/users/{id}/permissions`), devices, reference lists, import, settings, audit log with filters |

Interactive docs at `/docs` when the server runs.
