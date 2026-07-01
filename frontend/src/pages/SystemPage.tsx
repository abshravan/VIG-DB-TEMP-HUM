import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchSimulationStatus,
  fetchSystemHealth,
  setSimulatedPlcConnection,
  setSimulatedTagFailure,
  setSimulatedTagValue,
} from "../api/endpoints";
import { useAuthStore } from "../store/authStore";
import { useLiveStore } from "../store/liveStore";
import type { SimulatedTag } from "../types/api";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unitIndex = 0;
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024;
    unitIndex += 1;
  }
  return `${value.toFixed(1)} ${units[unitIndex]}`;
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${days}d ${hours}h ${minutes}m`;
}

export function SystemPage() {
  const liveHealth = useLiveStore((state) => state.systemHealth);
  const healthQuery = useQuery({ queryKey: ["system-health"], queryFn: fetchSystemHealth, refetchInterval: 15000 });
  const role = useAuthStore((state) => state.role);
  const canControlSimulation = role === "ADMIN" || role === "OPERATOR";

  const health = liveHealth ?? healthQuery.data;

  if (!health) {
    return <p className="text-sm text-slate-500">Loading…</p>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-base font-semibold text-slate-200">System</h2>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Gauge label="CPU" percent={health.cpu_percent} />
        <Gauge label="Memory" percent={health.memory_percent} />
        <Gauge label="Disk" percent={health.disk_percent} />
        <Stat label="Database size" value={formatBytes(health.database_size_bytes)} />
        <Stat label="Uptime" value={formatUptime(health.uptime_seconds)} />
        <Stat label="PLC connection" value={health.plc_connected ? "Connected" : "Disconnected"} />
      </div>
      <p className="text-xs text-slate-500">Server time: {new Date(health.server_time).toLocaleString()}</p>
      <SimulationPanel canControl={canControlSimulation} />
    </div>
  );
}

/** Only renders anything when the backend is actually running PLC_PROTOCOL=simulated —
 * against a real PLC there's nothing here to control, so the panel silently disappears
 * instead of showing an inactive/greyed-out feature.
 */
function SimulationPanel({ canControl }: { canControl: boolean }) {
  const queryClient = useQueryClient();
  const statusQuery = useQuery({
    queryKey: ["simulation-status"],
    queryFn: fetchSimulationStatus,
    refetchInterval: 5000,
    retry: false,
  });

  if (!statusQuery.data?.active) {
    return null;
  }

  const { plc_offline, tags } = statusQuery.data;

  async function refresh() {
    await queryClient.invalidateQueries({ queryKey: ["simulation-status"] });
  }

  async function handleTogglePlcOffline(disconnected: boolean) {
    await setSimulatedPlcConnection(disconnected);
    await refresh();
  }

  return (
    <div className="space-y-3 rounded-lg border border-amber-700/40 bg-amber-950/20 p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h3 className="text-sm font-semibold text-amber-300">PLC simulation</h3>
          <p className="text-xs text-slate-400">
            Running against a simulated PLC (PLC_PROTOCOL=simulated) — no real hardware is connected.
          </p>
        </div>
        {canControl && (
          <label className="flex shrink-0 items-center gap-2 text-xs text-slate-300">
            <input
              type="checkbox"
              checked={plc_offline}
              onChange={(e) => handleTogglePlcOffline(e.target.checked)}
            />
            Simulate PLC offline
          </label>
        )}
      </div>
      <div className="overflow-hidden rounded-lg border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead className="bg-slate-900/60 text-slate-400">
            <tr>
              <th className="px-4 py-2 font-medium">Tag</th>
              <th className="px-4 py-2 font-medium">Type</th>
              <th className="px-4 py-2 font-medium">Value</th>
              {canControl && <th className="px-4 py-2 font-medium">Sensor failure</th>}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {tags.map((tag) => (
              <SimulatedTagRow key={tag.name} tag={tag} canControl={canControl} onChanged={refresh} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SimulatedTagRow({
  tag,
  canControl,
  onChanged,
}: {
  tag: SimulatedTag;
  canControl: boolean;
  onChanged: () => Promise<void>;
}) {
  const [pendingValue, setPendingValue] = useState("");

  async function handleSetValue() {
    if (pendingValue === "") return;
    await setSimulatedTagValue(tag.name, Number(pendingValue));
    setPendingValue("");
    await onChanged();
  }

  async function handleToggleDigital(value: boolean) {
    await setSimulatedTagValue(tag.name, value);
    await onChanged();
  }

  async function handleToggleFailing(failing: boolean) {
    await setSimulatedTagFailure(tag.name, failing);
    await onChanged();
  }

  return (
    <tr className="text-slate-200">
      <td className="px-4 py-2 font-mono text-xs text-slate-400">{tag.name}</td>
      <td className="px-4 py-2 text-slate-400">{tag.sensor_type}</td>
      <td className="px-4 py-2">
        {tag.kind === "digital" ? (
          canControl ? (
            <input
              type="checkbox"
              checked={tag.current_value === true}
              onChange={(e) => handleToggleDigital(e.target.checked)}
            />
          ) : (
            tag.current_value === true ? "On" : "Off"
          )
        ) : canControl ? (
          <div className="flex items-center gap-2">
            <input
              type="number"
              placeholder={typeof tag.current_value === "number" ? tag.current_value.toFixed(1) : "—"}
              value={pendingValue}
              onChange={(e) => setPendingValue(e.target.value)}
              min={tag.eng_min ?? undefined}
              max={tag.eng_max ?? undefined}
              step="0.1"
              className="w-24 rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-sm"
            />
            <span className="text-xs text-slate-500">{tag.unit}</span>
            {pendingValue !== "" && (
              <button
                type="button"
                onClick={handleSetValue}
                className="rounded-md bg-sky-600 px-2 py-1 text-xs font-medium text-white hover:bg-sky-500"
              >
                Set
              </button>
            )}
          </div>
        ) : (
          `${typeof tag.current_value === "number" ? tag.current_value.toFixed(1) : "—"} ${tag.unit ?? ""}`
        )}
      </td>
      {canControl && (
        <td className="px-4 py-2">
          <input type="checkbox" checked={tag.failing} onChange={(e) => handleToggleFailing(e.target.checked)} />
        </td>
      )}
    </tr>
  );
}

function Gauge({ label, percent }: { label: string; percent: number }) {
  const color = percent > 90 ? "bg-red-500" : percent > 75 ? "bg-amber-500" : "bg-sky-500";
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-slate-500">{label}</span>
        <span className="text-lg font-semibold text-slate-100">{percent.toFixed(0)}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
        <div className={`h-full ${color}`} style={{ width: `${Math.min(percent, 100)}%` }} />
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-lg font-semibold text-slate-100">{value}</div>
    </div>
  );
}
