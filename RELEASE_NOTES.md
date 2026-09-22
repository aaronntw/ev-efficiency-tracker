## v1.4.3

- Editing a charging record now returns to the page where the edit started. Edits from Records return to Records with refreshed data (issue #12).
- Added an accessible light/dark mode switch in the header, including themed charts, tooltips, tables, forms, and status messages (issue #13).
- The first visit follows the browser color preference. An explicit selection persists in the same browser; switching preserves unsaved input.
- Added desktop and mobile browser regression coverage.

Container: `ghcr.io/aaronntw/ev-efficiency-tracker:v1.4.3`

The release workflow verifies an anonymous GHCR pull and checks the running container's health, version, and commit before publishing this release. No database schema changes are required.

To upgrade, back up the database, use the versioned image above, and recreate the container. Remove an old `APP_VERSION` environment override or set it to `1.4.3` so the displayed version matches the image.
