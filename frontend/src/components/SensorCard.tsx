import type { LiveSensor } from "../types/api";

const ICON_BY_TYPE: Record<string, string> = {
  TEMPERATURE: "🌡️",
  HUMIDITY: "💧",
  SMOKE: "🔥",
  WATER_LEAK: "🚰",
  DOOR: "🚪",
  CUSTOM: "📟",
};

function formatValue(sensor: LiveSensor): string {
  if (sensor.value === null) return "—";
  if (sensor.sensor_type === "DOOR") return sensor.value >= 0.5 ? "OPEN" : "CLOSED";
  if (sensor.sensor_type === "SMOKE") return sensor.value >= 0.5 ? "DETECTED" : "Clear";
  if (sensor.sensor_type === "WATER_LEAK") return sensor.value >= 0.5 ? "LEAK" : "Dry";
  return `${sensor.value.toFixed(1)}${sensor.unit ?? ""}`;
}

function isAlarmingDigital(sensor: LiveSensor): boolean {
  return ["DOOR", "SMOKE", "WATER_LEAK"].includes(sensor.sensor_type) && (sensor.value ?? 0) >= 0.5;
}

export function SensorCard({ sensor }: { sensor: LiveSensor }) {
  const alarming = isAlarmingDigital(sensor);
  const badQuality = sensor.quality === "BAD";

  return (
    <div
      className={`rounded-lg border p-4 ${
        alarming
          ? "border-red-500/40 bg-red-500/10"
          : sensor.is_stale || badQuality
            ? "border-amber-500/30 bg-slate-900/60"
            : "border-slate-700 bg-slate-900/60"
      }`}
    >
      <div className="flex items-center justify-between">
        <span className="text-sm text-slate-400">{sensor.display_name}</span>
        <span className="text-lg" aria-hidden>
          {ICON_BY_TYPE[sensor.sensor_type] ?? "📟"}
        </span>
      </div>
      <div className={`mt-2 text-2xl font-semibold ${alarming ? "text-red-400" : "text-slate-100"}`}>
        {formatValue(sensor)}
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
        {sensor.is_stale && <span className="text-amber-400">stale</span>}
        {badQuality && <span className="text-amber-400">bad reading</span>}
        {sensor.timestamp && !sensor.is_stale && (
          <span>{new Date(sensor.timestamp).toLocaleTimeString()}</span>
        )}
      </div>
    </div>
  );
}
