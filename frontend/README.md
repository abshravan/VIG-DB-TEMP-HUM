# frontend/

React + Vite + TypeScript dashboard, built to a static bundle and served by nginx in production (see [ARCHITECTURE.md §3.3](../docs/architecture/ARCHITECTURE.md#33-frontend-react--vite-not-nextjs) for why Vite over Next.js on Pi hardware). **Implemented.**

| Path | Purpose |
|---|---|
| `src/pages/` | One component per route: `LoginPage`, `DashboardPage`, `HistoryPage`, `EventsPage`, `SettingsPage`, `SystemPage`. |
| `src/components/` | Shared UI: `Layout` (nav shell + connection badges), `ProtectedRoute`, `SensorCard`, `SeverityBadge`, `ConnectionStatusBadge`. |
| `src/hooks/` | `useWebSocket` — connects to `/ws/live`, feeds every frame into the live store, reconnects with capped backoff on drop. |
| `src/store/` | Zustand: `authStore` (JWT tokens, persisted to localStorage, decodes username/role from the access token) and `liveStore` (live sensor values, PLC/alarm/health state — hydrated from the initial REST fetch, then kept current by WebSocket frames). |
| `src/api/` | `client.ts` — axios instance with a request interceptor that attaches the JWT and a response interceptor that transparently refreshes on 401 (at most one refresh in flight, everything else awaits it). `endpoints.ts` — typed wrapper per REST endpoint. |
| `src/charts/` | `HistoryChart` — ECharts, tree-shaken to just `LineChart` + `GridComponent` + `TooltipComponent` + `CanvasRenderer` (not the full bundle) since this ships to a resource-constrained Pi. |
| `src/types/api.ts` | TypeScript types mirroring `backend/app/schemas/*.py` and `backend/app/models/enums.py`. |

## Notable implementation decisions

- **State**: Zustand for live/auth state (simple, no boilerplate), TanStack Query for REST data fetching/caching/refetch-on-interval. Split cleanly: Query owns "what did the server say last," Zustand owns "what's true right now" (merged from Query's initial hydration + WebSocket deltas).
- **Auth**: JWT access token decoded client-side (`atob` on the payload) just to read `username`/`role` for the UI — never trusted for anything security-relevant, since every real authorization decision is enforced server-side.
- **CSV export**: fetched as a blob via axios (so the JWT can be attached — a plain `<a href>` can't send an Authorization header) and downloaded via an in-memory object URL.
- **Dev proxy**: `vite.config.ts` proxies `/api` and `/ws` to `http://127.0.0.1:8000`, mirroring the nginx reverse-proxy setup used in production so the frontend code never needs to know the backend's origin, in dev or prod.

## Verified

Migrated + seeded a real backend, ran `uvicorn` and `vite dev` together, and drove the app in a real headless Chromium (not just `tsc`/build passing): logged in, confirmed all five pages render real data with zero console errors, confirmed the alarm acknowledge flow actually changes state, and confirmed the WebSocket connects and the "Live feed" badge reflects it. Caught and fixed a real bug this way — `echarts-for-react`'s CJS `lib/core` entry point produced a broken component under Vite's dev-server ESM interop (blank page, `Element type is invalid`); switched to its `esm/core` entry, which works correctly.
