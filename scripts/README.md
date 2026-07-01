# scripts/

Operational scripts, run on the Raspberry Pi host (outside the containers) or via cron/systemd timers.

| Script (to be added) | Purpose |
|---|---|
| `backup.sh` | Invokes the backend's SQLite online-backup routine, rotates snapshots (14 daily + 12 monthly). See [ARCHITECTURE.md §12](../docs/architecture/ARCHITECTURE.md#12-backup-strategy). |
| `restore.sh` | Restores the database from a chosen backup snapshot; stops services first, restores, restarts. |
| `deploy.sh` | Raspberry Pi OS bootstrap: installs Docker, enables the Docker systemd service, clones/pulls the repo, brings up `docker compose`. |
