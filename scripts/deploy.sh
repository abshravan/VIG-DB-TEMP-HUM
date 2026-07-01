#!/usr/bin/env bash
# Raspberry Pi OS bootstrap: installs Docker if missing, enables it at boot, and brings up
# the monitoring stack. Safe to re-run — every step is idempotent.
#
# Usage: scripts/deploy.sh [repo-dir]  (defaults to the repo this script lives in)
set -euo pipefail

REPO_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DOCKER_DIR="$REPO_DIR/docker"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not found — installing via the official convenience script..."
    curl -fsSL https://get.docker.com | sh
fi

echo "Enabling Docker to start on boot..."
sudo systemctl enable docker

if [ ! -f "$DOCKER_DIR/.env" ]; then
    echo "No docker/.env found — copying from .env.example."
    echo "IMPORTANT: edit docker/.env now and set a real JWT_SECRET_KEY before continuing"
    echo "(generate one with: python3 -c \"import secrets; print(secrets.token_urlsafe(48))\")"
    cp "$DOCKER_DIR/.env.example" "$DOCKER_DIR/.env"
    exit 1
fi

if grep -q "REPLACE_ME_WITH_A_REAL_RANDOM_SECRET" "$DOCKER_DIR/.env"; then
    echo "docker/.env still has the placeholder JWT_SECRET_KEY — set a real secret before deploying." >&2
    exit 1
fi

cd "$DOCKER_DIR"
echo "Building and starting the stack..."
docker compose up -d --build

echo "Waiting for the backend to become healthy..."
for _ in $(seq 1 30); do
    status="$(docker compose ps --format json backend 2>/dev/null | grep -o '"Health":"[a-z]*"' | cut -d'"' -f4 || true)"
    if [ "$status" = "healthy" ]; then
        echo "Backend is healthy."
        break
    fi
    sleep 2
done

echo "Seeding the database (safe to re-run — existing data is left untouched)..."
docker compose exec -T backend python database/seed/seed.py

echo "Done. Dashboard: http://<this-pi's-address>/  (default admin password is set via SEED_ADMIN_PASSWORD in docker/.env — change it after first login)"
