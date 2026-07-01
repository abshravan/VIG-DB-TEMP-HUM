# docker/

Deployment definitions. See [ARCHITECTURE.md §11](../docs/architecture/ARCHITECTURE.md#11-deployment-docker-compose) for the full reasoning.

| File (to be added) | Purpose |
|---|---|
| `docker-compose.yml` | Two services: `backend` (FastAPI + poller + workers) and `frontend` (nginx serving the Vite build, reverse-proxying `/api` and `/ws`). Both `restart: unless-stopped`. |
| `docker-compose.override.yml` | Local development overrides (hot reload, exposed dev ports). |
| `.env.example` | Template for required environment variables (PLC IP/protocol, JWT secret, DB path, Atlas connection string) — copied to `.env` per deployment, never committed with real values. |
