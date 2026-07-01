import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useWebSocket } from "../hooks/useWebSocket";
import { useAuthStore } from "../store/authStore";
import { useLiveStore } from "../store/liveStore";
import { ConnectionStatusBadge } from "./ConnectionStatusBadge";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard" },
  { to: "/history", label: "History" },
  { to: "/events", label: "Events" },
  { to: "/settings", label: "Settings" },
  { to: "/system", label: "System" },
];

export function Layout() {
  const wsStatus = useWebSocket();
  const plcConnected = useLiveStore((state) => state.plcConnected);
  const activeAlarmCount = useLiveStore((state) => state.activeAlarmCount);
  const username = useAuthStore((state) => state.username);
  const role = useAuthStore((state) => state.role);
  const clearAuth = useAuthStore((state) => state.clear);
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 bg-slate-900/60">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-4">
          <div className="flex items-center gap-8">
            <h1 className="text-lg font-semibold tracking-tight">Server Room Monitor</h1>
            <nav className="flex gap-1">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                      isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:text-slate-200"
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-5">
            {activeAlarmCount > 0 && (
              <span className="rounded-full bg-red-500/20 px-3 py-1 text-xs font-semibold text-red-400">
                {activeAlarmCount} active alarm{activeAlarmCount === 1 ? "" : "s"}
              </span>
            )}
            <ConnectionStatusBadge label="PLC" connected={plcConnected} />
            <ConnectionStatusBadge label="Live feed" connected={wsStatus === "open"} pending={wsStatus === "reconnecting"} />
            <div className="flex items-center gap-3 border-l border-slate-800 pl-5 text-sm">
              <span className="text-slate-400">
                {username} <span className="text-slate-600">({role})</span>
              </span>
              <button
                type="button"
                onClick={() => {
                  clearAuth();
                  navigate("/login");
                }}
                className="rounded-md px-2 py-1 text-slate-400 hover:bg-slate-800 hover:text-slate-100"
              >
                Log out
              </button>
            </div>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
