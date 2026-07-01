import { useQuery } from "@tanstack/react-query";
import { fetchSystemHealth } from "../api/endpoints";
import { useLiveStore } from "../store/liveStore";

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
    </div>
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
