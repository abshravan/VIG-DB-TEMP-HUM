#!/usr/bin/env bash
# On-demand SQLite backup (the same routine BackupWorker runs automatically every night —
# see ARCHITECTURE.md §12). Useful before an upgrade, or just to confirm backups are working.
#
# Usage: scripts/backup.sh [docker-dir]  (defaults to <repo>/docker)
set -euo pipefail

DOCKER_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../docker" && pwd)}"
cd "$DOCKER_DIR"

docker compose exec -T backend python -c "
import asyncio
from app.core.time import utcnow
from app.workers.backup import BackupWorker

async def main():
    result = await BackupWorker().run_once(utcnow())
    if result is None:
        print('Backup skipped: no database file found.')
        raise SystemExit(1)
    print(f'Backup written: {result}')

asyncio.run(main())
"
