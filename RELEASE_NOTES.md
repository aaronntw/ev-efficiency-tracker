## v1.4.4 — October security update

- Refresh the frontend build runtime to Node.js 22.23.4 and production Python to 3.12.15, with immutable Docker base image pins.
- Update pip to 26.2.2 using Python's published SHA-256 bootstrap, refresh system certificates and Debian security packages, and enforce the patched Nginx/certificate-store package floors.
- Update Vite to 7.3.7 and source-map-js to 1.2.2.
- Upgrade FastAPI to 0.162.0, Starlette to 1.10.0 and Psycopg to 3.3.6; lock all Python dependencies with distribution hashes.
- Pin GitHub Actions to full commits, disable persisted checkout credentials, and separate read-only validation from publishing.
- Add SQLite/PostgreSQL API regressions, Basic Auth container checks, automated dependency audits, SBOM/provenance generation, and weekly dependency update checks.
- Keep authentication configuration consistent across both Compose files.

Container: `ghcr.io/aaronntw/ev-efficiency-tracker:v1.4.4`

No database schema changes are required. Back up the database, pull the versioned image,
and recreate the container while preserving volumes and environment settings. Remove
an old APP_VERSION override or set it to 1.4.4.

This release updates the application image. Operators must separately maintain their
external PostgreSQL server, host operating system, container runtime and TLS reverse proxy.
The release workflow verifies tests, security version floors, image pull, health,
application version and build SHA before creating this release.
