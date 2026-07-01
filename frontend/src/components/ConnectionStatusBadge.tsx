interface Props {
  label: string;
  connected: boolean;
  pending?: boolean;
}

export function ConnectionStatusBadge({ label, connected, pending }: Props) {
  const color = pending ? "bg-amber-400" : connected ? "bg-emerald-400" : "bg-red-400";
  const text = pending ? "Reconnecting…" : connected ? "Connected" : "Disconnected";
  return (
    <div className="flex items-center gap-2 text-sm text-slate-300">
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
      <span className="text-slate-400">{label}:</span>
      <span className="font-medium text-slate-200">{text}</span>
    </div>
  );
}
