#!/usr/bin/env bash
# Restores the database from a backup snapshot (ARCHITECTURE.md §12). Stops the backend,
# swaps in the chosen snapshot (dropping any stale WAL/SHM sidecar files so the replaced
# database isn't accidentally merged with leftover write-ahead-log entries), then restarts.
#
# Usage: scripts/restore.sh <backup-filename> [docker-dir]
# Run with no arguments to list available backups.
set -euo pipefail

BACKUP_FILE="${1:-}"
DOCKER_DIR="${2:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../docker" && pwd)}"
cd "$DOCKER_DIR"

if [ -z "$BACKUP_FILE" ]; then
    echo "Available backups:"
    docker compose run --rm --no-deps backend sh -c \
        "ls -1 /app/backups/monitoring-*.db 2>/dev/null | xargs -n1 basename" || echo "(none found)"
    echo
    echo "Usage: scripts/restore.sh <backup-filename>"
    exit 1
fi

echo "Stopping backend..."
docker compose stop backend

echo "Restoring $BACKUP_FILE..."
docker compose run --rm --no-deps backend sh -c "
    test -f /app/backups/$BACKUP_FILE || { echo 'backup file not found: $BACKUP_FILE'; exit 1; }
    cp /app/backups/$BACKUP_FILE /app/data/monitoring.db
    rm -f /app/data/monitoring.db-wal /app/data/monitoring.db-shm
"

echo "Restarting backend..."
docker compose up -d backend

echo "Restore complete."
