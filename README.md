# EV Efficiency Tracker

A self-hosted web application for tracking EV charging sessions, energy use, cost, and efficiency. Data remains under the operator's control and can be stored in SQLite or PostgreSQL.

**Current version:** v1.4.4

## Features

- Charging records with local date/time, AC/DC connector, odometer, state of charge, energy, cost, provider, location, and notes
- Dashboard filters for all time, month, year, and custom date ranges
- Efficiency, cost-per-distance, energy, spend, and AC/DC breakdowns
- Configurable vehicle, battery capacity, range, currency, and charging providers
- Persistent light/dark theme switch with browser preference on first visit
- CSV export and optional HTTP Basic Authentication
- SQLite and PostgreSQL backends

Calculated values are displayed to exactly two decimal places. Full precision is retained for storage and calculations.

## First-run configuration

Fresh installations use neutral example settings (`My EV`, 60 kWh, 400 km, and `USD`) and no region-specific providers. Open **Settings** after first launch and enter the correct values for your vehicle and region. Existing installations retain their stored settings and providers.

Usable battery capacity must be greater than 10 kWh and no more than 300 kWh. This validation is enforced by both the browser and API.

## Charging timestamps

Set `TZ` to the deployment's IANA timezone, such as `Asia/Kuala_Lumpur`. The frontend interprets entered wall-clock values in that timezone, converts them to UTC for storage, and converts stored UTC timestamps back to `TZ` for display and editing. Existing records are not automatically shifted during upgrade because their original timezone provenance is unknown.

## Docker Compose with SQLite

SQLite is the simplest single-user deployment. Persist `/data`, which contains `/data/ev_tracker.db` by default.

```yaml
services:
  ev-tracker:
    build: .
    image: ev-efficiency-tracker:v1.4.4
    ports:
      - "4886:80"
    volumes:
      - ./data:/data
    environment:
      APP_VERSION: "1.4.4"
      TZ: "Asia/Kuala_Lumpur"
      DB_TYPE: "sqlite"
      SQLITE_PATH: "/data/ev_tracker.db"
      WEB_AUTH_ENABLED: "${WEB_AUTH_ENABLED:-false}"
      WEB_AUTH_USERNAME: "${WEB_AUTH_USERNAME:-}"
      WEB_AUTH_PASSWORD: "${WEB_AUTH_PASSWORD:-}"
    restart: unless-stopped
```

Create an untracked `.env` file if authentication is enabled:

```env
WEB_AUTH_ENABLED=true
WEB_AUTH_USERNAME=your-user
WEB_AUTH_PASSWORD=use-a-secret-manager-or-strong-password
```

Run `docker compose up -d`, then open `http://localhost:4886`.

## Docker Compose with PostgreSQL

PostgreSQL deployments do not require an EV Tracker `/data` volume because application data is stored in PostgreSQL.

```yaml
services:
  ev-tracker:
    build: .
    image: ev-efficiency-tracker:v1.4.4
    ports:
      - "4886:80"
    environment:
      APP_VERSION: "1.4.4"
      TZ: "Asia/Kuala_Lumpur"
      DB_TYPE: "postgres"
      POSTGRES_HOST: "${POSTGRES_HOST}"
      POSTGRES_PORT: "${POSTGRES_PORT:-5432}"
      POSTGRES_DB: "${POSTGRES_DB}"
      POSTGRES_USER: "${POSTGRES_USER}"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
      WEB_AUTH_ENABLED: "${WEB_AUTH_ENABLED:-false}"
      WEB_AUTH_USERNAME: "${WEB_AUTH_USERNAME:-}"
      WEB_AUTH_PASSWORD: "${WEB_AUTH_PASSWORD:-}"
    restart: unless-stopped
```

Use a dedicated PostgreSQL role and database; do not commit their real names or credentials. Test connectivity at `/api/health`.

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `APP_VERSION` | `1.4.4` | Displayed application version |
| `APP_BUILD_SHA` | `unknown` | Optional build commit identifier |
| `TZ` | `UTC` | IANA timezone used by the frontend, for example `Asia/Kuala_Lumpur` |
| `DB_TYPE` | `sqlite` | `sqlite` or `postgres` |
| `SQLITE_PATH` | `/data/ev_tracker.db` | SQLite database path |
| `POSTGRES_HOST` | required for PostgreSQL | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | required for PostgreSQL | PostgreSQL database |
| `POSTGRES_USER` | required for PostgreSQL | PostgreSQL user |
| `POSTGRES_PASSWORD` | required for PostgreSQL | PostgreSQL password |
| `WEB_AUTH_ENABLED` | `false` | Enable HTTP Basic Authentication |
| `WEB_AUTH_USERNAME` | required when enabled | Basic Auth username |
| `WEB_AUTH_PASSWORD` | required when enabled | Basic Auth password |

## SQLite to PostgreSQL migration

Back up the SQLite file and target database first. The target PostgreSQL `charges` table must be empty.

```powershell
docker run --rm `
  --entrypoint python `
  -v "${PWD}/data:/data" `
  -e DB_TYPE=postgres `
  -e POSTGRES_HOST="${env:POSTGRES_HOST}" `
  -e POSTGRES_PORT="${env:POSTGRES_PORT}" `
  -e POSTGRES_DB="${env:POSTGRES_DB}" `
  -e POSTGRES_USER="${env:POSTGRES_USER}" `
  -e POSTGRES_PASSWORD="${env:POSTGRES_PASSWORD}" `
  ev-efficiency-tracker:v1.4.4 `
  -m backend.app.migrate_sqlite_to_postgres /data/ev_tracker.db
```

Verify `/api/charges`, `/api/settings`, and `/api/providers` after migration.

## Upgrade from v1.4.3

v1.4.4 refreshes the October 2026 security fixes: Node 22.23.4, Python 3.12.15,
pip 26.2.2, Vite 7.3.7, source-map-js 1.2.2, FastAPI 0.162.0,
Starlette 1.10.0, and Psycopg 3.3.6. Python dependencies are locked with
distribution hashes. Production builds refresh Debian security updates and
verify the Nginx and certificate-store security floors.

No database schema change is required. Back up your database, pull
`ghcr.io/aaronntw/ev-efficiency-tracker:v1.4.4`, and recreate the container.
Pulling alone does not replace a running container. Keep your existing volumes,
database connection settings, timezone, and authentication configuration.
This release does not update an external PostgreSQL server, reverse proxy, or host OS.

## Upgrade from v1.4.2

1. Back up the database.
2. Pull `ghcr.io/aaronntw/ev-efficiency-tracker:v1.4.4` and recreate the container.
3. Remove any old `APP_VERSION` environment override or set it to `1.4.4`.
4. Existing data is preserved; no schema migration is needed.

The header switch changes between light and dark themes without losing form input. Your selection is saved in this browser. The first visit follows your browser color preference. Editing a record returns to the page where the edit started.

## Older upgrade notes (v1.4.1)

1. Back up the database.
2. Build or pull v1.4.4 and recreate the container.
3. Existing data, settings, and providers are preserved.
4. Review the configured battery capacity; values outside `(10, 300]` must be corrected before Settings can be saved.
5. Set `TZ` before entering new records. Existing timestamps are not modified; new and edited records are stored in UTC and displayed in `TZ`.

## Development

```bash
git clone https://github.com/aaronntw/ev-efficiency-tracker.git
cd ev-efficiency-tracker
docker build --build-arg APP_VERSION=1.4.4 -t ev-efficiency-tracker:v1.4.4 .
```

Regression tests: `cd frontend && npm ci && npx playwright install chromium && npx playwright test`.

Pull requests run API checks against SQLite and PostgreSQL, desktop/mobile browser tests,
both dependency-lock audits, and a fresh Linux container build with Basic Auth checks.
Pushes to `main` run the same checks before publishing a new versioned image,
verifying its pull and health/version, promoting it to `latest`, and creating the
version tag and GitHub release. Bump the application version for every release.
Existing version tags cannot be overwritten by this automatic path.

Use the Node version in `.node-version`. Install backend dependencies with
`python -m pip install --require-hashes --only-binary=:all: -r backend/requirements.txt`
after updating pip to at least 26.2.2. Run API regressions from the repository root:
`python -m unittest discover -s backend/tests -v`. Tests use a temporary SQLite
database unless PostgreSQL test connection variables are explicitly supplied.

Edit `backend/requirements.in` for direct Python dependencies, then regenerate
`backend/requirements.txt` using uv >=0.13.4:
`uv pip compile --universal --python-version 3.12 --generate-hashes --output-file backend/requirements.txt backend/requirements.in`.
Review and audit the resulting full lockfile. Docker base images and GitHub Actions
are pinned to immutable digests/commits; Dependabot checks for weekly updates.

The stack uses React/Vite, FastAPI, SQLAlchemy, Nginx, and Docker.

## Security

- Never commit `.env` files, passwords, tokens, database dumps, application data, exports, or logs.
- Use HTTPS and appropriate reverse-proxy/access controls for Internet exposure.
- Before making a previously private repository public, scan the complete Git history. Removing a file from the current tree does not remove it from earlier commits.

## License

See the repository license file for licensing information.

