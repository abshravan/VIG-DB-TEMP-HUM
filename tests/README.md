# tests/

Cross-cutting end-to-end tests that exercise the whole stack (PLC simulator → backend → frontend), as opposed to `backend/tests/unit` and `backend/tests/integration` which test the backend in isolation.

| Path | Purpose |
|---|---|
| `e2e/` | Full-stack scenarios: simulate a PLC value change, assert it reaches the dashboard via WebSocket; simulate PLC disconnect, assert a `PLC_OFFLINE` alarm appears after the grace period; verify CSV export matches stored history. |
