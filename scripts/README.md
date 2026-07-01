# scripts/

Operational scripts, run on the Raspberry Pi host (outside the containers) or via cron/systemd timers. **Implemented.**

| Script | Purpose |
|---|---|
| `deploy.sh` | Raspberry Pi OS bootstrap: installs Docker if missing (official convenience script), enables it at boot, checks `docker/.env` exists and its JWT secret isn't still the placeholder, brings the stack up, waits for the backend healthcheck, then seeds the database. Idempotent — safe to re-run. |
| `backup.sh` | Triggers the same `BackupWorker` routine that runs automatically every night (see [ARCHITECTURE.md §12](../docs/architecture/ARCHITECTURE.md#12-backup-strategy)) on demand, via `docker compose exec` — useful right before an upgrade, or just to confirm backups are actually working. |
| `restore.sh` | Restores the database from a chosen backup snapshot: stops the backend, swaps in the snapshot (dropping stale WAL/SHM sidecar files), restarts. Run with no arguments to list the backups available inside the `backups` volume. |

All three assume `docker/docker-compose.yml` is the active stack and are meant to be run from a checkout of this repository on the Pi (or wherever the stack is deployed) — not from inside a container.
