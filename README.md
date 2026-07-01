# Industrial Server Room Monitoring System

Production monitoring system for a basement server room: Siemens S7-1200 PLC → Raspberry Pi → local dashboard, LAN-only with optional internet historical sync.

**Start here:** [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md) — the full architecture, every design decision and its rationale, database schema, API design, and the module-by-module implementation roadmap.

## Project structure

| Folder | Purpose |
|---|---|
| [`backend/`](backend/README.md) | FastAPI application: PLC communication, validation, alarm engine, REST API, WebSocket, background workers. |
| [`frontend/`](frontend/README.md) | React + Vite dashboard (Dashboard, History, Events, Settings, System pages). |
| [`database/`](database/README.md) | Migration history mirror and seed data for local/dev database bootstrap. |
| [`docker/`](docker/README.md) | Docker Compose deployment definitions and environment templates. |
| [`docs/`](docs/README.md) | Architecture and operational documentation. |
| [`scripts/`](scripts/README.md) | Operational scripts: backup, restore, Raspberry Pi deployment. |
| [`tests/`](tests/README.md) | Cross-cutting end-to-end tests (unit/integration tests live inside `backend/tests`). |
| [`config/`](config/README.md) | Runtime configuration handed to us by the PLC team: tag maps, example alarm rules. |

## Status

All 9 modules of the implementation roadmap are complete (database layer, PLC communication, validation + alarm engine, REST API, WebSocket real-time layer, frontend dashboard, background workers, Docker Compose deployment, and a hardening pass covering crash-recovery, rate limiting, structured logging, and a WebSocket auth redesign). See [`docs/architecture/ARCHITECTURE.md` §17](docs/architecture/ARCHITECTURE.md#17-implementation-roadmap-module-by-module-each-production-ready-before-the-next) for what each module covers and how it was verified.
