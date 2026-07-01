# database/

The database's source of truth is `backend/app/models/` + `backend/alembic/`. This folder holds artifacts that live *alongside* the schema rather than defining it:

| Path | Purpose |
|---|---|
| `migrations/` | Mirror of applied Alembic migration history kept for reference/audit outside the backend container (the authoritative migration scripts live in `backend/alembic/versions/`). |
| `seed/` | Seed data for local/dev bootstrap: default admin user, example sensors matching `config/plc_tags.yaml`, default alarm rules. Never used against the production Pi without explicit operator action. |
