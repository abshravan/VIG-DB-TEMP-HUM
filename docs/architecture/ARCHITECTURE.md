# Industrial Server Room Monitoring System — Architecture

**Status:** Design approved for implementation, module-by-module.
**Scope:** Basement server room monitored via Siemens S7-1200 PLC → Raspberry Pi → local dashboard, LAN-only, internet-optional for historical sync.

This document is the single source of truth for architectural decisions. Every module built afterward must conform to what's described here. If a decision needs to change during implementation, this file gets updated first.

---

## 1. Guiding Constraints (why the design looks the way it does)

1. **LAN-only, offline-first.** The Pi must fully function — polling, alarms, dashboard, storage — with zero internet. Internet is an optional *enhancement* (Atlas sync), never a dependency. This rules out any architecture that requires a cloud round-trip for core function (no cloud-hosted broker, no SaaS auth, no CDN-loaded frontend assets).
2. **Single Raspberry Pi, constrained resources.** Typically a Pi 4 (4GB) or Pi 5. CPU/RAM/SD-card I/O are the scarce resources, not developer convenience. Every choice below is filtered through "does this run comfortably on a Pi 24/7 for years."
3. **One site, one Pi.** This is not a multi-tenant, multi-Pi fleet product (yet). That means we can make simplifying choices (single-process backend, SQLite, no message broker) that would be wrong at fleet scale — and we design the seams (repository pattern, DB-agnostic ORM, abstracted PLC client) so it can grow later without a rewrite.
4. **Safety-relevant data.** Smoke, water leak, door, PLC-offline are not "nice to have" metrics — they gate a physical alarm workflow. The architecture treats digital safety signals with faster polling, debounce logic, and a state machine, not just as another chart series.
5. **PLC protocol is not finalized.** The PLC team may deliver either S7 or Modbus TCP. The architecture must not hard-code one — a `PLCClient` abstraction (Strategy pattern) with two interchangeable implementations means we don't block on their decision.

---

## 2. High-Level Architecture

```
┌─────────────────────────┐
│   Siemens S7-1200 PLC   │  (temperature, humidity, smoke, water leak, door — via DB or Modbus regs)
└────────────┬─────────────┘
             │ Ethernet (LAN), S7 protocol (port 102) OR Modbus TCP (port 502)
             ▼
┌───────────────────────────────────────────────────────────────────┐
│                       Raspberry Pi (Docker Compose)                │
│                                                                     │
│  ┌───────────────────────────── backend container ──────────────┐ │
│  │                                                                │ │
│  │   PLC Client (snap7 / pymodbus, behind common interface)       │ │
│  │        │  raw values                                           │ │
│  │        ▼                                                       │ │
│  │   Poller Worker (asyncio task, tiered polling)                 │ │
│  │        │  scaled engineering values + timestamps                │ │
│  │        ▼                                                       │ │
│  │   Validation Layer (range/rate/staleness checks, quality flag) │ │
│  │        │                                                       │ │
│  │        ├──────────────► Alarm Engine (rule eval, state machine)│ │
│  │        ▼                                                       │ │
│  │   Repository Layer  ──────────────►  SQLite (WAL mode)         │ │
│  │        │                                                       │ │
│  │        ▼                                                       │ │
│  │   FastAPI (REST /api/v1/*, JWT auth)                           │ │
│  │        │                                                       │ │
│  │        ▼                                                       │ │
│  │   WebSocket Broadcaster (/ws/live) ◄── Alarm Engine events     │ │
│  │                                                                │ │
│  │   Background workers: backup, rollup/retention, Atlas sync     │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                          │ REST + WS (proxied)                       │
│  ┌────────────────────── frontend container (nginx) ──────────────┐│
│  │   React + Vite static build — Dashboard/History/Events/Settings ││
│  └──────────────────────────────────────────────────────────────────┘
└───────────────────────────────────────────────────────────────────┘
             │ (only when internet is available, best-effort, async)
             ▼
     MongoDB Atlas (optional historical mirror — never a dependency)
```

Data flow, restated as the pipeline requested:

```
PLC → PLC Client → Poller (tiered) → Validation Layer → Repository → SQLite
                                             │
                                             ▼
                                       Alarm Engine
                                             │
                              ┌──────────────┴──────────────┐
                              ▼                              ▼
                        REST API (pull)              WebSocket (push)
                                             │
                                             ▼
                                     React Dashboard
```

---

## 3. Technology Decisions & Rationale

### 3.1 PLC protocol: S7 (python-snap7) vs Modbus TCP (pymodbus)

| | S7 protocol (`python-snap7`) | Modbus TCP (`pymodbus`) |
|---|---|---|
| PLC-side effort | None beyond exposing a DB — but **must disable "Optimized block access"** on that DB (Properties → Attributes), otherwise byte offsets aren't stable and snap7 can't read it. Must also enable "Permit access with PUT/GET communication" under Protection & Security. | PLC team must add an `MB_SERVER` instruction (TIA Portal, firmware ≥ V4.1) and explicitly map each tag to a Modbus register. More PLC engineering work, but works with optimized DBs since the instruction — not raw memory offsets — does the mapping. |
| Client complexity | Read raw bytes at DB offsets, unpack with `snap7.util` (REAL/INT/BOOL). Requires a tag map (DB#, offset, type) from the PLC team. | Read holding/coil registers by address. Slightly more "standard" (works identically against any brand of PLC, not just Siemens). |
| Failure mode if PLC team's DB layout changes | Byte offsets shift silently → wrong values unless DB is re-optimized-off and offsets re-confirmed. | Register map is explicit and versioned in the PLC program; less fragile to unrelated DB edits. |
| Best fit here | **Recommended default** — client explicitly said "preferred if simpler," and it is: no extra ladder/SCL logic needed on their side, just one flag flipped on an existing DB. | Good fallback if the PLC team prefers not to touch DB optimization settings, or if they're more comfortable exposing Modbus (common in mixed-vendor sites). |

**Decision:** Build a `PLCClient` abstract interface (`connect()`, `disconnect()`, `read_all_tags()`, `is_connected()`) with two implementations — `S7PLCClient` and `ModbusPLCClient` — selected by a single config value (`PLC_PROTOCOL=s7|modbus`). Default to S7/snap7. This means the PLC team's final protocol choice is a config change, not a rewrite. Tag mapping (DB/register, data type, scaling, poll tier) lives in `config/plc_tags.yaml`, not in code — the PLC team hands us the map, we don't hand-edit Python for every point.

### 3.2 Database: SQLite now, PostgreSQL-ready later

SQLite because: zero extra process on a resource-constrained Pi, single file for trivial backup, WAL mode gives good concurrent read/write for this write-light (~1 reading/few seconds/sensor) workload. PostgreSQL would be overkill for one site and adds a container + RAM overhead for no real benefit at this scale.

To make swapping to Postgres later a config change, not a rewrite:
- SQLAlchemy 2.0 async ORM (`aiosqlite` driver now, `asyncpg` later) — no raw SQL, no SQLite-only functions.
- Alembic migrations written against the ORM models, which are dialect-agnostic (`Integer`, `Float`, `String`, `DateTime`, `Boolean`, `Enum` — no `JSON1`, no `ROWID` tricks).
- Repository pattern isolates all query code from the rest of the app — if a Postgres-only optimization is ever wanted, it's contained to the repository implementation.
- Avoid SQLite-specific concurrency assumptions in application logic (e.g., don't rely on single-writer behavior).

### 3.3 Frontend: React + Vite (not Next.js)

Next.js's main advantages — SSR, SEO, edge rendering — are irrelevant for an authenticated, LAN-only, internal dashboard with no public pages to index. Its cost on a Pi is real: a Next.js production deployment needs a persistent Node server process (or a much heavier build/output setup for static export with caveats around dynamic routes and API routes). React + Vite instead compiles to a **pure static bundle**, served by a tiny `nginx` container — a few MB of RAM instead of a running Node runtime, faster cold start, and a smaller Docker image. Given the app is 100% client-rendered against a REST/WebSocket API (not content that benefits from server rendering), Vite is the practical choice for this hardware target.

### 3.4 REST + WebSocket (not GraphQL, not polling-only, not gRPC)

- REST is simple, cacheable, and matches the CRUD-shaped resources here (sensors, history, alarms, settings, users) — no need for GraphQL's query flexibility for a fixed, small set of screens.
- WebSocket for live push (readings, alarm transitions, PLC status) avoids REST polling overhead on a low-power device and gives sub-second UI updates, which matters for smoke/water-leak/door alarms.
- No message broker (Redis/RabbitMQ/MQTT) — with a single backend process and a single frontend audience (the LAN dashboard), an in-process `asyncio` pub/sub (a `ConnectionManager` broadcasting to connected `WebSocket` clients) is sufficient and removes a whole extra service to run/monitor/backup on the Pi. Revisit only if this grows into a multi-Pi fleet with a central aggregator.

### 3.5 Single backend process, not split microservices

The PLC poller and the REST/WebSocket API run as **asyncio tasks inside one FastAPI process** (started from the `lifespan` context), not as separate containers. Reasons:
- SQLite is much happier with one writer process than several containers fighting over file locks.
- On a single Pi there's no scaling benefit to splitting them — it would only add IPC complexity (would need a queue or shared DB polling to hand data from a separate poller container to the API container).
- Internally the code is still modular (`app/plc`, `app/workers`, `app/api` are separate packages with clean boundaries) so splitting into separate services later, if a fleet-management use case emerges, is a deployment change, not a redesign.

### 3.6 Auth: JWT, still enforced despite LAN-only

Even though the dashboard never leaves the LAN, this is a physical-safety-relevant system (smoke, water leak, door, environmental thresholds for hardware protecting infra) — insider mistakes and shared terminals are still a risk. JWT (short-lived access token + refresh token) with bcrypt-hashed passwords and three roles (`admin`, `operator`, `viewer`) is cheap to build and prevents "anyone on the LAN can silently change alarm thresholds or acknowledge a real smoke alarm."

**Implementation note:** both tokens are stateless JWTs — access tokens expire in 30 minutes (default), refresh tokens in 7 days, and there is no server-side revocation list. `POST /auth/logout` exists for API symmetry but the client discarding its tokens is what actually "logs out"; an admin deactivating a user (`is_active=False`) or changing their password stops *future* logins but doesn't invalidate an already-issued unexpired token. This is a deliberate v1 simplification bounded by the short access-token lifetime — a token blacklist (e.g. a `revoked_tokens` table checked in `get_current_user`) is the natural next step if that exposure window ever matters more than the added complexity.

---

## 4. PLC Communication Layer

### 4.1 Abstraction

```python
class PLCClient(Protocol):
    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def read_tags(self, tags: list[TagDefinition]) -> dict[str, RawValue]: ...
    def is_connected(self) -> bool: ...
```

`S7PLCClient` wraps `python-snap7` (`client.db_read(db_number, start, size)` + `snap7.util.get_real/get_bool/get_int`). `ModbusPLCClient` wraps `pymodbus` (`read_holding_registers` / `read_coils`). Both are synchronous libraries under the hood — calls are wrapped in `asyncio.to_thread` so a slow/hung PLC socket never blocks the event loop (and therefore never blocks the API or WebSocket from serving already-known data).

### 4.2 Tag map (`config/plc_tags.yaml`)

Given by the PLC team, consumed without code changes:

```yaml
tags:
  - name: temp_rack_a
    kind: analog
    sensor_type: TEMPERATURE
    s7: { db: 10, offset: 0, type: REAL }
    modbus: { register: 40001, type: FLOAT32 }
    scale: { raw_min: 0, raw_max: 27648, eng_min: 0, eng_max: 50, unit: "°C" }
    poll_tier: normal
  - name: door_main
    kind: digital
    sensor_type: DOOR
    s7: { db: 10, offset: 40, bit: 0 }
    modbus: { register: 1, type: COIL }
    poll_tier: fast
```

### 4.3 Tiered polling

- **Fast tier (default 500 ms–1 s):** smoke, water leak, door — safety-relevant digital signals.
- **Normal tier (default 2–5 s, configurable):** temperature, humidity, other analog values.

Each tier is its own `asyncio` loop so a slow analog scan never delays a smoke-detector read.

### 4.4 Resilience

Connection state machine: `DISCONNECTED → CONNECTING → CONNECTED → ERROR`. On failure: exponential backoff reconnect (1s, 2s, 5s, 10s, 30s cap), circuit breaker to stop hammering a PLC that's mid-reboot. Readings taken while disconnected are never fabricated — the last-known value is flagged `STALE` after `poll_interval × missed_cycles`, and a `PLC_OFFLINE` alarm fires only after a configurable grace period (default 10 s) to avoid false trips on a one-cycle network blip.

---

## 5. Validation Layer

Implemented in `backend/app/services/validation.py` (`ReadingValidator`). Every raw read is judged before it reaches the database:
1. **Read failure (decode error, PLC rejected the request)** → no numeric value exists, so nothing is stored; it's counted toward a per-tag failure streak instead (see `SENSOR_FAILURE` below).
2. **Range check** — a successfully-decoded analog value outside its tag's configured engineering span (plus a margin — default 20% — for legitimate excursions) → `BAD`.
3. **Rate-of-change check** — a value moving more than a configurable fraction of its span (default 50%) in one poll cycle is far more likely a sensor/wiring fault than reality → `BAD`. A `BAD` reading does not update the "last known good" value used for the *next* cycle's rate check, so one implausible spike can't drag the baseline off course.
4. **Digital tags** always pass straight through as `GOOD` (decoded true/false, no numeric range/rate applies).
5. Every successfully-decoded reading — `GOOD` or `BAD` — is written to `SensorReading` with its quality tag, so history shows *why* a value looks off rather than leaving a silent gap. Only `GOOD` readings are fed to the Alarm Engine.
6. **Staleness** is not written into stored rows (a freshly-written reading is never itself stale) — it's a live-status query (`ReadingValidator.is_stale`, comparing "now" against the last known-good timestamp), used by "live" views (Module 4/5) and by the `SENSOR_FAILURE`/`PLC_OFFLINE` alarms below.

---

## 6. Database Schema

```
Sensor ──1:N── SensorReading
Sensor ──1:N── SensorReadingHourly / SensorReadingDaily (rollups)
Sensor ──1:N── AlarmRule
AlarmRule ──1:N── Alarm
Sensor ──1:N── Alarm (nullable — some alarms, e.g. PLC_OFFLINE, aren't sensor-scoped)
User ──1:N── Alarm (acknowledged_by, nullable)
User ──1:N── Configuration (updated_by, nullable)
User ──1:N── SystemLog (actor, nullable — many SystemLog entries are system-generated)
```

| Table | Key columns | Notes |
|---|---|---|
| **Sensor** | `id PK`, `tag_name` (unique, matches `plc_tags.yaml`), `display_name`, `sensor_type` (enum: TEMPERATURE/HUMIDITY/SMOKE/WATER_LEAK/DOOR/CUSTOM), `unit`, `location`, `is_active`, `created_at`, `updated_at` | Display name/location editable from Settings without touching the tag map. |
| **SensorReading** | `id PK`, `sensor_id FK`, `value`, `quality` (GOOD/BAD/STALE), `timestamp` (indexed), `synced_at` (nullable — Atlas sync outbox marker) | Raw time series. Retention-limited (§9). |
| **SensorReadingHourly / …Daily** | `sensor_id FK`, `bucket_start`, `min`, `max`, `avg`, `sample_count` | Rollups so long-range history graphs don't scan millions of raw rows or bloat SD storage. |
| **AlarmRule** | `id PK`, `sensor_id FK` (nullable — global rules like PLC_OFFLINE), `alarm_type` (TEMP_HIGH/TEMP_LOW/HUMIDITY_HIGH/HUMIDITY_LOW/SMOKE/DOOR_OPEN/WATER_LEAK/PLC_OFFLINE/SENSOR_FAILURE), `threshold_value` (nullable for digital), `hysteresis`, `min_duration_seconds` (debounce), `severity` (INFO/WARNING/CRITICAL), `is_enabled` | The configurable-threshold requirement lives here, editable via Settings. |
| **Alarm** | `id PK`, `rule_id FK`, `sensor_id FK` (nullable), `state` (ACTIVE/ACKNOWLEDGED/CLEARED), `triggered_value`, `triggered_at`, `acknowledged_at`, `acknowledged_by FK→User` (nullable), `cleared_at`, `message` | One row per alarm *instance/episode*, not per poll — this is the Events/alarm-history table. |
| **User** | `id PK`, `username` (unique), `hashed_password`, `role` (ADMIN/OPERATOR/VIEWER), `is_active`, `created_at`, `last_login_at` | |
| **SystemLog** | `id PK`, `timestamp`, `level` (INFO/WARNING/ERROR/CRITICAL), `category` (PLC_CONNECTION/SYSTEM_RESTART/AUTH/CONFIG_CHANGE/BACKUP), `message`, `meta` (JSON text) | Connection failures, restarts, config changes, backup outcomes — the Events page "system logs" tab. |
| **Configuration** | `key PK`, `value`, `value_type`, `updated_at`, `updated_by FK→User` (nullable) | Runtime-editable settings (poll interval, sensor display names default, session timeout, Atlas sync toggle). |

---

## 7. REST API Design

All under `/api/v1`, JSON, JWT bearer auth (except `/auth/login`).

**Auth**
- `POST /auth/login` — returns access + refresh token
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`

**Live**
- `GET /live` — snapshot: all sensors' latest value/quality, PLC connection status, Pi health summary, active alarm count
- `GET /live/{sensor_id}`

**History**
- `GET /history?sensor_id=&start=&end=&resolution=raw|hourly|daily`
- `GET /history/export?...` — CSV stream

**Alarms / Events**
- `GET /alarms?state=&severity=&start=&end=`
- `POST /alarms/{id}/acknowledge`
- `GET /events` — SystemLog feed (connection failures, restarts, config changes)

**Sensors**
- `GET /sensors`
- `POST /sensors` (admin)
- `PATCH /sensors/{id}` (admin/operator — display name, location)

**Settings**
- `GET /settings` / `PUT /settings` — poll interval, session timeout, etc.
- `GET /settings/alarm-rules` / `PUT /settings/alarm-rules/{id}` — thresholds, hysteresis, debounce, severity

**Users** (admin only)
- `GET /users`, `POST /users`, `PATCH /users/{id}`, `DELETE /users/{id}`

**System**
- `GET /system/health` — CPU%, RAM%, disk%, SQLite file size, uptime, PLC status

**WebSocket**
- `WS /ws/live` — pushes `{"type": "reading"|"alarm"|"plc_status"|"system_health", "data": {...}}` frames; the same envelope shape the frontend store consumes for all four dashboard live-update needs.

**Implementation note:** `ConnectionManager` (`backend/app/realtime/connection_manager.py`) is the in-process pub/sub broadcaster from §3.4 — created once in `create_app()` (not inside the PLC lifespan) so `/ws/live` works independently of whether the PLC poller is running. Browsers can't set a custom `Authorization` header on a WebSocket handshake, so auth is `?token=<jwt access token>` as a query parameter, validated the same way as REST (`decode_token` + an active-user check) before `accept()`. `ReadingIngestionService` broadcasts a `reading` frame after every stored poll cycle and an `alarm` frame whenever `AlarmEngine.evaluate()` reports a state change (it now returns the changed `Alarm` or `None` for exactly this); `plc_status` is broadcast on every `ResilientPLCConnection` state change; `system_health` is pushed every 10s by a small background task (`app/realtime/health_broadcaster.py`), skipped entirely when no client is connected. Verified against a real `uvicorn` process and a real `websockets` client (not just the test suite) — connect, then receive a live `system_health` frame over the wire.

---

## 8. Alert System

State machine per alarm instance: `(no row) → ACTIVE → ACKNOWLEDGED / CLEARED` (an operator can acknowledge while still active; it clears the instant the underlying condition recovers past the hysteresis band — no separate clear-debounce). Implemented in `backend/app/services/alarm_engine.py` (`AlarmEngine`) — a single long-lived instance holds the in-memory per-rule debounce/open-alarm state across poll cycles; repositories are passed into its methods rather than owned by it, since a DB session is scoped per poll cycle, not per process.

- **Hysteresis (deadband):** e.g. TEMP_HIGH trips at 30°C, clears only below 28°C — prevents rapid flapping around the exact threshold. Threshold-style alarms (`TEMP_HIGH/LOW`, `HUMIDITY_HIGH/LOW`) use this; boolean-style alarms (`SMOKE`, `DOOR_OPEN`, `WATER_LEAK`, `PLC_OFFLINE`, `SENSOR_FAILURE`) have no deadband — they clear the instant the condition is false.
- **Debounce:** condition must hold for `min_duration_seconds` before an alarm fires — prevents a single noisy sample from creating an alarm. Resets if the condition drops before the debounce window elapses.
- **Severity:** INFO/WARNING/CRITICAL drives dashboard styling and (future) notification routing.
- Covers all nine required types: Temp High/Low, Humidity High/Low, Smoke, Door Open, Water Leak, PLC Offline, Sensor Failure. `PLC_OFFLINE` is driven by `ResilientPLCConnection`'s state changes (via `ReadingIngestionService.handle_connection_state_change`); `SENSOR_FAILURE` is driven by a per-tag consecutive-read-failure streak (default threshold: 3) reaching its limit, via `ReadingIngestionService.handle_readings` — both call the same `AlarmEngine.evaluate` as the numeric threshold alarms, just with a 1.0/0.0 boolean condition instead of an engineering-unit value.
- `ReadingIngestionService` (`backend/app/services/ingestion.py`) is the glue wired as the `PLCPoller`'s `on_readings` callback: validate → store `SensorReading` → evaluate alarm rules for that sensor, all inside one DB session per poll cycle.

---

## 9. Historical Logging & Retention

Raw `SensorReading` rows are kept for a configurable window (default 90 days), then a nightly worker rolls them into `SensorReadingHourly`/`SensorReadingDaily` aggregates and prunes the raw rows older than the window — keeping the History page's long-range charts fast and the SD card from filling up.

**Implementation note:** `RetentionWorker` (`backend/app/workers/retention.py`) buckets in Python (fetch the recent window, group by hour/day) rather than a dialect-specific SQL date-trunc, so it runs unchanged against SQLite or PostgreSQL; each bucket is checked for existence first (`get_bucket`) so re-running the job is harmless. Deliberately does **not** run `VACUUM` as part of the nightly job — it's a blocking, whole-database-locking operation that could stall the app for multiple seconds on a Pi with a large history; WAL mode already checkpoints automatically in the background (`app/core/database.py`'s PRAGMAs), and a full `VACUUM` is left as a manual/rare maintenance operation rather than an automated one.

---

## 10. Configuration Management

Two tiers, deliberately different lifecycles:
- **Infra-level** (`.env`, loaded once via `pydantic-settings`): DB path, PLC IP/rack/slot, ports, JWT secret, Atlas connection string. Changing these requires a restart — they're deployment facts, not runtime tuning.
- **Runtime-level** (`Configuration` table, editable from the Settings page without restart): poll interval, sensor display names, alarm thresholds/hysteresis/debounce, Atlas sync on/off. The poller and alarm engine read an in-memory cache of this table, invalidated the moment `PUT /settings` succeeds — so a threshold change takes effect on the next poll cycle, not after a redeploy.

---

## 11. Deployment (Docker Compose)

Two services:
- **`backend`** — FastAPI + poller + workers in one container (§3.5). Volume-mounts the SQLite file and log directory onto the host so they survive container recreation and are reachable by the backup script. `restart: unless-stopped`. Healthcheck hits `GET /system/health` and fails if the last successful PLC poll is older than N cycles.
- **`frontend`** — nginx serving the Vite static build, reverse-proxying `/api` and `/ws` to `backend`. `restart: unless-stopped`.

Networking: standard Docker bridge network is sufficient — the poller only makes *outbound* connections to the PLC's LAN IP (port 102 or 502), which works fine through the bridge/NAT; host networking isn't needed since the PLC never needs to initiate a connection back into the container. Only the frontend's port 80/443 is published to the LAN.

---

## 12. Backup Strategy

- **Local (always on):** nightly job uses SQLite's online backup API (`sqlite3 .backup`, not a raw file copy, so it's crash-consistent even against a live WAL) to a timestamped file under a `/backups` volume; rotation keeps the last 14 daily snapshots, plus one representative per month for up to 12 months beyond that. Implemented in `backend/app/workers/backup.py` (`BackupWorker`), verified with real temp SQLite files (backup, restore, and multi-month rotation), not just mocked.
- **Remote (optional, best-effort):** an outbox pattern — `SensorReading` carries a nullable `synced_at` (v1 syncs sensor history only, not `Alarm`/`SystemLog` — the highest-volume, most useful-for-offsite-analysis data, and the simplest case to get right; extending the same pattern to the other tables is a small, separate step if ever needed). `AtlasSyncWorker` (`backend/app/workers/atlas_sync.py`) runs every 60s by default, batch-upserting unsynced rows via `motor` (async MongoDB driver) and marking them synced only on success; any failure (no internet, unreachable Atlas, bad credentials) is logged and retried next cycle, never raised. Disabled by default (empty `ATLAS_CONNECTION_STRING`) — this worker is fully decoupled from the core write path, so if it's disabled or the internet is down for a month, ingestion/alarms/dashboard are entirely unaffected; the backlog just grows locally until connectivity returns.

---

## 13. Error Handling & Resilience

- PLC layer: backoff + circuit breaker (§4.4).
- API layer: global exception handlers → structured JSON logs, no unhandled 500s leak stack traces to the client.
- Frontend: WebSocket client auto-reconnects with backoff and shows a "Reconnecting…" banner instead of silently going stale.
- Docker healthchecks restart a container that's stopped producing fresh data, without operator intervention.

---

## 14. Recovery After Power Failure

- Docker daemon enabled via `systemctl enable docker`; all services `restart: unless-stopped` — on power restoration the Pi boots, Docker starts, containers start, no manual step required.
- SQLite in WAL mode with `PRAGMA synchronous=NORMAL`: safe automatic recovery from an unclean shutdown without a manual repair step.
- Startup logs a `SYSTEM_RESTART` `SystemLog` entry; a `clean_shutdown` marker file (removed at startup, rewritten by a graceful-shutdown handler) lets us tell a clean restart apart from a crash/power-loss in that log entry.
- Hardware recommendation (not software-enforced): a small UPS/PoE with battery buys time for graceful shutdown and protects the SD card from a write-in-progress power cut.

---

## 15. Security

JWT access + refresh tokens, bcrypt/argon2 password hashing, RBAC (`admin`/`operator`/`viewer`), login rate-limiting, JWT secret from `.env` only (never committed). HTTPS via an internal/self-signed cert is recommended even on LAN, since credentials still traverse the network in plaintext otherwise.

---

## 16. Coding Standards

- SOLID + Repository Pattern (`app/repositories`) + Dependency Injection via FastAPI `Depends` — services and routers depend on repository *interfaces*, making unit tests swap in an in-memory SQLite or fakes trivially.
- Full type hints, Pydantic v2 schemas for every request/response (`app/schemas`), never raw dicts across a boundary.
- `asyncio` throughout the backend; blocking PLC I/O isolated via `asyncio.to_thread`.
- Structured logging (JSON), unit tests per module (`backend/tests/unit`) plus integration tests (`backend/tests/integration`, `tests/e2e`) exercising the full poll → validate → store → API path against an in-memory PLC simulator.
- All secrets/environment-specific values via `.env` (see `docker/.env.example`), never hard-coded.

---

## 17. Implementation Roadmap (module-by-module, each production-ready before the next)

1. ✅ **Database layer** — SQLAlchemy models, Alembic migrations, repositories, seed data.
2. ✅ **PLC communication layer** — `PLCClient` interface + S7 implementation (default) + Modbus implementation, tag map loader, tiered poller, connection resilience — tested against a simulator before real PLC access is available.
3. ✅ **Validation layer + Alarm engine** — quality flags, rule evaluation, state machine.
4. ✅ **REST API** — auth, live/history/alarms/sensors/settings/users/system endpoints.
5. ✅ **WebSocket real-time layer**.
6. ✅ **Frontend** — Dashboard, then History, Events, Settings, System pages.
7. ✅ **Background workers** — retention/rollup, local backup, optional Atlas sync.
8. **Docker Compose deployment** + Raspberry Pi OS setup script.
9. **Hardening pass** — resilience/error-handling review, recovery-after-power-failure drill, security review.

This order is deliberate: the database and PLC layers are the foundation everything else reads from, so they're built and proven first; the frontend comes after the API contract is stable so it isn't built against a moving target.
