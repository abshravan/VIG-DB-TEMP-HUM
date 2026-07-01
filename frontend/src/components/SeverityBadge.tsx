import type { AlarmSeverity } from "../types/api";

const STYLES: Record<AlarmSeverity, string> = {
  CRITICAL: "bg-red-500/15 text-red-400 border-red-500/30",
  WARNING: "bg-amber-500/15 text-amber-400 border-amber-500/30",
  INFO: "bg-sky-500/15 text-sky-400 border-sky-500/30",
};

export function SeverityBadge({ severity }: { severity: AlarmSeverity }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${STYLES[severity]}`}>
      {severity}
    </span>
  );
}
