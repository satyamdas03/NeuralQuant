const VERDICT_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  "STRONG BUY":  { bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/30" },
  "BUY":         { bg: "bg-green-500/10",   text: "text-green-400",   border: "border-green-500/30" },
  "HOLD":        { bg: "bg-amber-500/10",   text: "text-amber-400",   border: "border-amber-500/30" },
  "SELL":        { bg: "bg-red-500/10",     text: "text-red-400",     border: "border-red-500/30" },
  "STRONG SELL": { bg: "bg-red-600/10",     text: "text-red-500",     border: "border-red-600/30" },
};

type Props = { verdict: string; confidence: number; timeframe: string };

export default function VerdictBanner({ verdict, confidence, timeframe }: Props) {
  const style = VERDICT_STYLES[verdict] ?? VERDICT_STYLES["HOLD"];
  return (
    <div className={`rounded-lg ${style.bg} border ${style.border} px-4 py-3 flex items-center justify-between flex-wrap gap-2`}>
      <div className="flex items-center gap-3">
        <span className={`text-sm font-bold tracking-wide ${style.text}`}>{verdict}</span>
        <span className="text-xs text-on-surface-variant">{timeframe}</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-on-surface-variant">Confidence</span>
        <div className="w-20 h-1.5 rounded-full bg-surface-container overflow-hidden">
          <div
            className={`h-full rounded-full ${style.text.replace("text-", "bg-")}`}
            style={{ width: `${confidence}%` }}
          />
        </div>
        <span className="text-xs tabular-nums text-on-surface-variant">{confidence}%</span>
      </div>
    </div>
  );
}