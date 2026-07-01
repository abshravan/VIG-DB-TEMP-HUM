import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { fetchAlarms, fetchEvents } from "../api/endpoints";
import { SeverityBadge } from "../components/SeverityBadge";
import type { AlarmSeverity, AlarmState } from "../types/api";

type Tab = "alarms" | "logs";

export function EventsPage() {
  const [tab, setTab] = useState<Tab>("alarms");
  const [stateFilter, setStateFilter] = useState<AlarmState | "">("");
  const [severityFilter, setSeverityFilter] = useState<AlarmSeverity | "">("");

  const alarmsQuery = useQuery({
    queryKey: ["alarms", "history", stateFilter, severityFilter],
    queryFn: () =>
      fetchAlarms({
        state: stateFilter || undefined,
        severity: severityFilter || undefined,
      }),
    enabled: tab === "alarms",
  });

  const logsQuery = useQuery({ queryKey: ["events"], queryFn: () => fetchEvents(200), enabled: tab === "logs" });

  return (
    <div className="space-y-6">
      <div className="flex gap-1">
        <TabButton active={tab === "alarms"} onClick={() => setTab("alarms")}>
          Alarm history
        </TabButton>
        <TabButton active={tab === "logs"} onClick={() => setTab("logs")}>
          System logs
        </TabButton>
      </div>

      {tab === "alarms" && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value as AlarmState | "")}
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100"
            >
              <option value="">All states</option>
              <option value="ACTIVE">Active</option>
              <option value="ACKNOWLEDGED">Acknowledged</option>
              <option value="CLEARED">Cleared</option>
            </select>
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value as AlarmSeverity | "")}
              className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100"
            >
              <option value="">All severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="WARNING">Warning</option>
              <option value="INFO">Info</option>
            </select>
          </div>

          <div className="overflow-hidden rounded-lg border border-slate-800">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-900/60 text-slate-400">
                <tr>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 font-medium">Severity</th>
                  <th className="px-4 py-2 font-medium">State</th>
                  <th className="px-4 py-2 font-medium">Triggered</th>
                  <th className="px-4 py-2 font-medium">Cleared</th>
                  <th className="px-4 py-2 font-medium">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {alarmsQuery.data?.map((alarm) => (
                  <tr key={alarm.id} className="text-slate-200">
                    <td className="px-4 py-2">{alarm.alarm_type}</td>
                    <td className="px-4 py-2">
                      <SeverityBadge severity={alarm.severity} />
                    </td>
                    <td className="px-4 py-2">{alarm.state}</td>
                    <td className="px-4 py-2 text-slate-400">{new Date(alarm.triggered_at).toLocaleString()}</td>
                    <td className="px-4 py-2 text-slate-400">
                      {alarm.cleared_at ? new Date(alarm.cleared_at).toLocaleString() : "—"}
                    </td>
                    <td className="px-4 py-2 text-slate-400">{alarm.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {alarmsQuery.data?.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-slate-500">No matching alarms.</p>
            )}
          </div>
        </div>
      )}

      {tab === "logs" && (
        <div className="overflow-hidden rounded-lg border border-slate-800">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900/60 text-slate-400">
              <tr>
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-4 py-2 font-medium">Level</th>
                <th className="px-4 py-2 font-medium">Category</th>
                <th className="px-4 py-2 font-medium">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {logsQuery.data?.map((log) => (
                <tr key={log.id} className="text-slate-200">
                  <td className="px-4 py-2 text-slate-400">{new Date(log.timestamp).toLocaleString()}</td>
                  <td className="px-4 py-2">{log.level}</td>
                  <td className="px-4 py-2">{log.category}</td>
                  <td className="px-4 py-2 text-slate-400">{log.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {logsQuery.data?.length === 0 && (
            <p className="px-4 py-6 text-center text-sm text-slate-500">No events recorded yet.</p>
          )}
        </div>
      )}
    </div>
  );
}

function TabButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md px-3 py-1.5 text-sm font-medium ${
        active ? "bg-slate-800 text-white" : "text-slate-400 hover:text-slate-200"
      }`}
    >
      {children}
    </button>
  );
}
