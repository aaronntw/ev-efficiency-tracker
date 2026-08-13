# EV Efficiency Tracker

A self-hosted web application for tracking EV charging sessions, energy use, cost, and efficiency. Data remains under the operator's control and can be stored in SQLite or PostgreSQL.

**Current version:** v1.4.2

## Features

- Charging records with local date/time, AC/DC connector, odometer, state of charge, energy, cost, provider, location, and notes
- Dashboard filters for all time, month, year, and custom date ranges
- Efficiency, cost-per-distance, energy, spend, and AC/DC breakdowns
- Configurable vehicle, battery capacity, range, currency, and charging providers
- CSV export and optional HTTP Basic Authentication
- SQLite and PostgreSQL backends

Calculated values are displayed to exactly two decimal places. Full precision is retained for storage and calculations.

## First-run configuration

Fresh installations use neutral example settings (`My EV`, 60 kWh, 400 km, and `USD`) and no region-specific providers. Open **Settings** after first launch and enter the correct values for your vehicle and region. Existing installations retain their stored settings and providers.

Usable battery capacity must be greater than 10 kWh and no more than 300 kWh. This validation is enforced by both the browser and API.

## Charging timestamps

Charging-session timestamps are stored as timezone-naive local wall-clock values. A value entered as `2024-12-31 16:49` is saved and displayed as `2024-12-31 16:49`; the application does not convert it to UTC. Existing records are not shifted during upgrade because their original timezone provenance is unknown.

## Docker Compose with SQLite

SQLite is the simplest single-user deployment. Persist `/data`, which contains `/data/ev_tracker.db` by default.

```yaml
services:
  ev-tracker:
    build: .
    image: ev-efficiency-tracker:v1.4.2
    ports:
      - "4886:80"
    volumes:
      - ./data:/data
    environment:
      APP_VERSION: "1.4.2"
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
    image: ev-efficiency-tracker:v1.4.2
    ports:
      - "4886:80"
    environment:
      APP_VERSION: "1.4.2"
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
| `APP_VERSION` | `1.4.2` | Displayed application version |
| `APP_BUILD_SHA` | `unknown` | Optional build commit identifier |
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
  ev-efficiency-tracker:v1.4.2 `
  -m backend.app.migrate_sqlite_to_postgres /data/ev_tracker.db
```

Verify `/api/charges`, `/api/settings`, and `/api/providers` after migration.

## Upgrade from v1.4.1

1. Back up the database.
2. Build or pull v1.4.2 and recreate the container.
3. Existing data, settings, and providers are preserved.
4. Review the configured battery capacity; values outside `(10, 300]` must be corrected before Settings can be saved.
5. Existing timestamps are not modified. New and edited records preserve the entered local wall-clock time.

## Development

```bash
git clone https://github.com/aaronntw/ev-efficiency-tracker.git
cd ev-efficiency-tracker
docker build --build-arg APP_VERSION=1.4.2 -t ev-efficiency-tracker:v1.4.2 .
```

The stack uses React/Vite, FastAPI, SQLAlchemy, Nginx, and Docker.

## Security

- Never commit `.env` files, passwords, tokens, database dumps, application data, exports, or logs.
- Use HTTPS and appropriate reverse-proxy/access controls for Internet exposure.
- Before making a previously private repository public, scan the complete Git history. Removing a file from the current tree does not remove it from earlier commits.

## License

See the repository license file for licensing information.
