# frontend/

React + Vite dashboard, built to a static bundle and served by nginx (see [ARCHITECTURE.md §3.3](../docs/architecture/ARCHITECTURE.md#33-frontend-react--vite-not-nextjs) for why Vite over Next.js on Pi hardware).

| Path | Purpose |
|---|---|
| `src/pages/` | One component per route: Dashboard, History, Events, Settings, System, Login. |
| `src/components/` | Shared UI: sensor cards, alarm banners, threshold forms, layout/nav shell. |
| `src/hooks/` | `useWebSocket` (auto-reconnecting live feed), `useAuth`, data-fetching hooks. |
| `src/store/` | Client state (Zustand) — live sensor values, connection status, active alarms — fed by both REST (initial load) and WebSocket (live updates). |
| `src/api/` | Typed REST client against `/api/v1/*`. |
| `src/charts/` | Apache ECharts wrapper components for time-series/history views. |

Nothing here is implemented yet — built after the backend REST/WebSocket API contract is stable (Module 6 in the roadmap), so the frontend isn't built against a moving target.
