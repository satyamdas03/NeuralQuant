import { neutralBand, type NeutralBand } from "@/lib/neutralLabels";

const BAND_STYLES: Record<NeutralBand, { bg: string; text: string; border: string }> = {
  "Upper band":  { bg: "bg-green-500/10", text: "text-green-400",           border: "border-green-500/30" },
  "Middle band": { bg: "bg-amber-500/10", text: "text-amber-400",           border: "border-amber-500/30" },
  "Lower band":  { bg: "bg-red-500/10",   text: "text-red-400",             border: "border-red-500/30" },
  "Unrated":     { bg: "bg-surface-container", text: "text-on-surface-variant", border: "border-outline-variant" },
};

type Props = { verdict: string; confidence: number; timeframe: string };

export default function VerdictBanner({ verdict, confidence, timeframe }: Props) {
  const band = neutralBand(verdict);
  const style = BAND_STYLES[band];
  return (
    <div className={`rounded-lg ${style.bg} border ${style.border} px-4 py-3 flex items-center justify-between flex-wrap gap-2`}>
      <div className="flex items-center gap-3">
        <span className={`text-sm font-bold tracking-wide ${style.text}`}>{band}</span>
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