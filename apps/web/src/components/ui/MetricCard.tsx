type Props = {
  label: string;
  value: string;
  subtext?: string;
  accent?: "primary" | "secondary" | "tertiary" | "error";
};

const ACCENT: Record<string, string> = {
  primary: "text-primary",
  secondary: "text-secondary",
  tertiary: "text-tertiary",
  error: "text-error",
};

export default function MetricCard({
  label,
  value,
  subtext,
  accent = "primary",
}: Props) {
  return (
    <div className="rounded-xl bg-surface-container ghost-border p-3">
      <p className="text-xs text-on-surface-variant">{label}</p>
      <p className={`tabular-nums text-xl font-bold ${ACCENT[accent]}`}>
        {value}
      </p>
      {subtext && (
        <p className="text-[10px] text-on-surface-variant">{subtext}</p>
      )}
    </div>
  );
}