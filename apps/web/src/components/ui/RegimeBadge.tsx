import type { RegimeLabel } from "@/lib/types";

const REGIME_STYLES: Record<RegimeLabel, { bg: string; text: string; dot: string }> = {
  "Risk-On":    { bg: "bg-tertiary-fixed/10",  text: "text-tertiary-fixed-dim",  dot: "bg-tertiary-fixed-dim" },
  "Recovery":   { bg: "bg-secondary/10", text: "text-secondary", dot: "bg-secondary" },
  "Late-Cycle": { bg: "bg-primary-fixed/10",   text: "text-primary-fixed",  dot: "bg-primary-fixed" },
  "Bear":       { bg: "bg-cyber-red/10",     text: "text-cyber-red",    dot: "bg-cyber-red" },
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
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 font-mono text-[10px] font-bold tracking-[0.2em] uppercase ${s.bg} ${s.text}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {r}
    </span>
  );
}
