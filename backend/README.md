# backend/

FastAPI application. Single process, multiple internal `asyncio` tasks (API server, PLC poller, background workers) — see [ARCHITECTURE.md §3.5](../docs/architecture/ARCHITECTURE.md#35-single-backend-process-not-split-microservices) for why this isn't split into multiple containers.

| Path | Purpose |
|---|---|
| `app/api/v1/` | FastAPI routers, one module per resource (auth, live, history, alarms, sensors, settings, users, system). Thin — validates input, delegates to services/repositories. |
| `app/core/` | Cross-cutting setup: `pydantic-settings` config loader, JWT/security helpers, logging configuration, app-wide constants. |
| `app/models/` | SQLAlchemy ORM models (dialect-agnostic — see [ARCHITECTURE.md §3.2](../docs/architecture/ARCHITECTURE.md#32-database-sqlite-now-postgresql-ready-later)). |
| `app/schemas/` | Pydantic request/response schemas. Nothing crosses an API or service boundary as a raw dict. |
| `app/repositories/` | Repository pattern — all DB queries live here, injected into services/routers via `Depends`. Swapping SQLite→PostgreSQL touches this layer, not callers. |
| `app/services/` | Business logic: alarm rule evaluation/state machine, configuration cache, CSV export, user management. |
| `app/plc/` | PLC communication layer: `PLCClient` interface, `S7PLCClient` (python-snap7), `ModbusPLCClient` (pymodbus), tag map loader. See [ARCHITECTURE.md §4](../docs/architecture/ARCHITECTURE.md#4-plc-communication-layer). |
| `app/realtime/` | WebSocket `ConnectionManager` — in-process broadcast of readings/alarms/status to connected dashboard clients. |
| `app/workers/` | Background asyncio tasks: poller loops (fast/normal tiers), retention/rollup job, local backup job, optional MongoDB Atlas sync. |
| `alembic/` | Database migrations, generated from `app/models`. |
| `tests/unit/` | Unit tests per module (repositories, services, PLC client against a simulator, alarm engine). |
| `tests/integration/` | Full pipeline tests: simulated PLC → poll → validate → store → API/WebSocket. |

Nothing here is implemented yet — this README describes the target layout from the architecture doc, filled in module by module per the roadmap.
