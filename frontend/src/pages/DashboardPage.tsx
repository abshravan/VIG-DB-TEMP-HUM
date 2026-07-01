import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { acknowledgeAlarm, fetchAlarms, fetchLiveStatus, fetchSystemHealth } from "../api/endpoints";
import { SensorCard } from "../components/SensorCard";
import { SeverityBadge } from "../components/SeverityBadge";
import { useLiveStore } from "../store/liveStore";

export function DashboardPage() {
  const hydrate = useLiveStore((state) => state.hydrate);
  const sensors = useLiveStore((state) => state.sensors);
  const lastUpdate = useLiveStore((state) => state.lastUpdate);
  const systemHealth = useLiveStore((state) => state.systemHealth);

  const liveQuery = useQuery({ queryKey: ["live"], queryFn: fetchLiveStatus, refetchInterval: 15000 });
  const alarmsQuery = useQuery({
    queryKey: ["alarms", "active"],
    queryFn: () => fetchAlarms({ state: "ACTIVE" }),
    refetchInterval: 5000,
  });
  const healthQuery = useQuery({ queryKey: ["system-health"], queryFn: fetchSystemHealth, refetchInterval: 30000 });

  useEffect(() => {
    if (liveQuery.data) hydrate(liveQuery.data);
  }, [liveQuery.data, hydrate]);

  const sensorList = Object.values(sensors);
  const health = systemHealth ?? healthQuery.data;

  async function handleAcknowledge(alarmId: number) {
    await acknowledgeAlarm(alarmId);
    await alarmsQuery.refetch();
  }

  return (
    <div className="space-y-8">
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-200">Sensors</h2>
          {lastUpdate && (
            <span className="text-xs text-slate-500">Last update: {new Date(lastUpdate).toLocaleTimeString()}</span>
          )}
        </div>
        {sensorList.length === 0 ? (
          <p className="text-sm text-slate-500">No sensors reporting yet.</p>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            {sensorList.map((sensor) => (
              <SensorCard key={sensor.sensor_id} sensor={sensor} />
            ))}
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-base font-semibold text-slate-200">Active alarms</h2>
        {!alarmsQuery.data || alarmsQuery.data.length === 0 ? (
          <p className="text-sm text-slate-500">No active alarms.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-900/60 text-slate-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 font-medium">Severity</th>
                  <th className="px-4 py-2 font-medium">Triggered</th>
                  <th className="px-4 py-2 font-medium">Message</th>
                  <th className="px-4 py-2 font-medium">State</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {alarmsQuery.data.map((alarm) => (
                  <tr key={alarm.id} className="text-slate-200">
                    <td className="px-4 py-2">{alarm.alarm_type}</td>
                    <td className="px-4 py-2">
                      <SeverityBadge severity={alarm.severity} />
                    </td>
                    <td className="px-4 py-2 text-slate-400">{new Date(alarm.triggered_at).toLocaleString()}</td>
                    <td className="px-4 py-2 text-slate-400">{alarm.message}</td>
                    <td className="px-4 py-2">{alarm.state}</td>
                    <td className="px-4 py-2 text-right">
                      {alarm.state === "ACTIVE" && (
                        <button
                          type="button"
                          onClick={() => handleAcknowledge(alarm.id)}
                          className="rounded-md bg-slate-800 px-2 py-1 text-xs font-medium text-slate-200 hover:bg-slate-700"
                        >
                          Acknowledge
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-base font-semibold text-slate-200">Raspberry Pi health</h2>
        {health ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <StatTile label="CPU" value={`${health.cpu_percent.toFixed(0)}%`} />
            <StatTile label="Memory" value={`${health.memory_percent.toFixed(0)}%`} />
            <StatTile label="Disk" value={`${health.disk_percent.toFixed(0)}%`} />
            <StatTile label="Uptime" value={formatUptime(health.uptime_seconds)} />
          </div>
        ) : (
          <p className="text-sm text-slate-500">Loading…</p>
        )}
      </section>
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 text-xl font-semibold text-slate-100">{value}</div>
    </div>
  );
}

function formatUptime(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}
