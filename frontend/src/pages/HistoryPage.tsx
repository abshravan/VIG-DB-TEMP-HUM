import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { downloadHistoryCsv, fetchHistory, fetchSensors } from "../api/endpoints";
import { HistoryChart } from "../charts/HistoryChart";
import type { HistoryParams } from "../api/endpoints";

function isoLocal(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function HistoryPage() {
  const sensorsQuery = useQuery({ queryKey: ["sensors"], queryFn: fetchSensors });

  const [sensorId, setSensorId] = useState<number | null>(null);
  const [resolution, setResolution] = useState<HistoryParams["resolution"]>("raw");
  const [start, setStart] = useState(() => isoLocal(new Date(Date.now() - 24 * 3600 * 1000)));
  const [end, setEnd] = useState(() => isoLocal(new Date()));
  const [downloading, setDownloading] = useState(false);

  const effectiveSensorId = sensorId ?? sensorsQuery.data?.[0]?.id ?? null;
  const selectedSensor = sensorsQuery.data?.find((s) => s.id === effectiveSensorId) ?? null;

  const params: HistoryParams | null = useMemo(() => {
    if (effectiveSensorId === null) return null;
    return {
      sensorId: effectiveSensorId,
      start: new Date(start).toISOString(),
      end: new Date(end).toISOString(),
      resolution,
    };
  }, [effectiveSensorId, start, end, resolution]);

  const historyQuery = useQuery({
    queryKey: ["history", params],
    queryFn: () => fetchHistory(params as HistoryParams),
    enabled: params !== null,
  });

  async function handleExport() {
    if (!params) return;
    setDownloading(true);
    try {
      const blob = await downloadHistoryCsv(params);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${selectedSensor?.tag_name ?? "history"}.csv`;
      link.click();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-base font-semibold text-slate-200">History</h2>

      <div className="flex flex-wrap items-end gap-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <Field label="Sensor">
          <select
            value={effectiveSensorId ?? ""}
            onChange={(e) => setSensorId(Number(e.target.value))}
            className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100"
          >
            {sensorsQuery.data?.map((sensor) => (
              <option key={sensor.id} value={sensor.id}>
                {sensor.display_name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="From">
          <input
            type="datetime-local"
            value={start}
            onChange={(e) => setStart(e.target.value)}
            className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100"
          />
        </Field>

        <Field label="To">
          <input
            type="datetime-local"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100"
          />
        </Field>

        <Field label="Resolution">
          <select
            value={resolution}
            onChange={(e) => setResolution(e.target.value as HistoryParams["resolution"])}
            className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100"
          >
            <option value="raw">Raw</option>
            <option value="hourly">Hourly</option>
            <option value="daily">Daily</option>
          </select>
        </Field>

        <button
          type="button"
          onClick={handleExport}
          disabled={downloading || !params}
          className="rounded-md bg-slate-800 px-3 py-1.5 text-sm font-medium text-slate-200 hover:bg-slate-700 disabled:opacity-50"
        >
          {downloading ? "Exporting…" : "Export CSV"}
        </button>
      </div>

      <div className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        {historyQuery.isLoading && <p className="text-sm text-slate-500">Loading…</p>}
        {historyQuery.data && historyQuery.data.length === 0 && (
          <p className="text-sm text-slate-500">No data in this range.</p>
        )}
        {historyQuery.data && historyQuery.data.length > 0 && (
          <HistoryChart points={historyQuery.data} unit={selectedSensor?.unit ?? null} />
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-slate-400">
      {label}
      {children}
    </label>
  );
}
