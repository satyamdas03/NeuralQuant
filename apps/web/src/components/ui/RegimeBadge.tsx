import type { RegimeLabel } from "@/lib/types";

const REGIME_STYLES: Record<RegimeLabel, { bg: string; text: string; dot: string }> = {
  "Risk-On":    { bg: "bg-tertiary/10",  text: "text-tertiary",  dot: "bg-tertiary" },
  "Recovery":   { bg: "bg-secondary/10", text: "text-secondary", dot: "bg-secondary" },
  "Late-Cycle": { bg: "bg-primary/10",   text: "text-primary",  dot: "bg-primary" },
  "Bear":       { bg: "bg-error/10",     text: "text-error",    dot: "bg-error" },
};

type Props = {
  regime?: RegimeLabel;
  label?: RegimeLabel;
};

export default function RegimeBadge({ regime, label }: Props) {
  const r = regime ?? label ?? "Bear";
  const s = REGIME_STYLES[r] ?? REGIME_STYLES["Bear"];

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${s.bg} ${s.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {r}
    </span>
  );
}