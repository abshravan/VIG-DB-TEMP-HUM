# docker/

Deployment definitions. See [ARCHITECTURE.md §11](../docs/architecture/ARCHITECTURE.md#11-deployment-docker-compose) for the full reasoning. **Implemented.**

| File | Purpose |
|---|---|
| `docker-compose.yml` | Two services: `backend` (built from `../backend/Dockerfile`, context = repo root so it can also bundle the seed script and default tag map) and `frontend` (nginx serving the Vite build, reverse-proxying `/api` and `/ws`). Both `restart: unless-stopped`. Named volumes `db-data`/`backups` persist the SQLite file and backup snapshots across container recreation; `config/plc_tags.yaml` is bind-mounted read-only so the PLC team's tag map can be edited without a rebuild. |
| `docker-compose.override.yml` | Auto-loaded local convenience: publishes the backend's port directly (bypassing the nginx proxy) and disables the restart loop while iterating. Day-to-day development still runs `uvicorn`/`vite dev` directly on the host (see `backend/README.md` and `frontend/README.md`) — this is for testing the actual container build before a Pi deployment. |
| `.env.example` | Template for required environment variables (PLC IP/protocol, JWT secret, seed admin password, Atlas connection string). Copy to `.env`, fill in a real `JWT_SECRET_KEY`, never commit the real file. `DATABASE_URL`/`TAG_MAP_PATH` are deliberately *not* here — they're pinned directly in `docker-compose.yml` to the container's mounted volume paths. |

## First-time setup

```sh
cd docker
cp .env.example .env
# edit .env: set a real JWT_SECRET_KEY (see the comment in the file for how to generate one),
# and PLC_ADDRESS/PLC_PROTOCOL once the PLC team confirms them.
docker compose up -d --build
docker compose exec backend python database/seed/seed.py   # creates the admin user + example sensors
```

Or run `../scripts/deploy.sh`, which does all of the above (plus installing Docker itself if it's missing) and is safe to re-run.

## Verifying this deployment

This session's sandbox has no outbound access to Docker Hub (confirmed — even `docker pull hello-world` is blocked by network policy), so `docker compose build`/`up` could not be executed end-to-end here. What **was** verified:
- `docker compose config` — the compose file parses correctly, merges with the override file as expected, and every environment variable/volume/network resolves to the intended value.
- Every `COPY` source path referenced by both Dockerfiles exists on disk.
- The application logic itself (everything these images package) was fully verified by running the backend (`uvicorn`) and frontend (`vite dev`) directly on the host against each other — see `backend/README.md` and `frontend/README.md` for what that covered.

Building and running this compose stack on an actual machine with registry access (a dev laptop, or the target Raspberry Pi) is the recommended next step before relying on it.
