# EV Efficiency Tracker

A self-hosted web application for tracking EV charging sessions, energy use, cost, and efficiency. Data remains under the operator's control and can be stored in SQLite or PostgreSQL.

**Current version:** v1.4.3

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
    image: ev-efficiency-tracker:v1.4.3
    ports:
      - "4886:80"
    volumes:
      - ./data:/data
    environment:
      APP_VERSION: "1.4.3"
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
    image: ev-efficiency-tracker:v1.4.3
    ports:
      - "4886:80"
    environment:
      APP_VERSION: "1.4.3"
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
| `APP_VERSION` | `1.4.3` | Displayed application version |
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
  ev-efficiency-tracker:v1.4.3 `
  -m backend.app.migrate_sqlite_to_postgres /data/ev_tracker.db
```

Verify `/api/charges`, `/api/settings`, and `/api/providers` after migration.

## Upgrade from v1.4.2

1. Back up the database.
2. Pull `ghcr.io/aaronntw/ev-efficiency-tracker:v1.4.3` and recreate the container.
3. Remove any old `APP_VERSION` environment override or set it to `1.4.3`.
4. Existing data is preserved; no schema migration is needed.

The header switch changes between light and dark themes without losing form input. Your selection is saved in this browser. The first visit follows your browser color preference. Editing a record returns to the page where the edit started.

## Older upgrade notes (v1.4.1)

1. Back up the database.
2. Build or pull v1.4.3 and recreate the container.
3. Existing data, settings, and providers are preserved.
4. Review the configured battery capacity; values outside `(10, 300]` must be corrected before Settings can be saved.
5. Set `TZ` before entering new records. Existing timestamps are not modified; new and edited records are stored in UTC and displayed in `TZ`.

## Development

```bash
git clone https://github.com/aaronntw/ev-efficiency-tracker.git
cd ev-efficiency-tracker
docker build --build-arg APP_VERSION=1.4.3 -t ev-efficiency-tracker:v1.4.3 .
```

Regression tests: `cd frontend && npm ci && npx playwright install chromium && npx playwright test`.

Updating `frontend/package.json` on `main` triggers the release workflow. It runs browser tests, builds and pushes the versioned image, verifies an anonymous pull and container health/version, promotes the image to `latest`, and creates the corresponding tag and GitHub release. Existing version tags cannot be overwritten by this automatic path.

The stack uses React/Vite, FastAPI, SQLAlchemy, Nginx, and Docker.

## Security

- Never commit `.env` files, passwords, tokens, database dumps, application data, exports, or logs.
- Use HTTPS and appropriate reverse-proxy/access controls for Internet exposure.
- Before making a previously private repository public, scan the complete Git history. Removing a file from the current tree does not remove it from earlier commits.

## License

See the repository license file for licensing information.

