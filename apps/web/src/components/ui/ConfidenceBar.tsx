type Props = {
  value: number;
  max?: number;
  label?: string;
  accent?: "primary" | "secondary" | "tertiary";
};

const ACCENT_MAP: Record<string, string> = {
  primary: "bg-primary",
  secondary: "bg-secondary",
  tertiary: "bg-tertiary",
};

export default function ConfidenceBar({
  value,
  max = 1,
  label,
  accent = "tertiary",
}: Props) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));

  return (
    <div className="w-full">
      {label && (
        <div className="mb-1 flex items-center justify-between text-xs">
          <span className="text-on-surface-variant">{label}</span>
          <span className="tabular-nums text-on-surface">
            {(value * 100).toFixed(0)}%
          </span>
        </div>
      )}
      <div className="h-1.5 w-full rounded-full bg-surface-high">
        <div
          className={`h-full rounded-full transition-all ${ACCENT_MAP[accent]}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}