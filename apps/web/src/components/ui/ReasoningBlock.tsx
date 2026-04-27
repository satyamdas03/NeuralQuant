import type { ReasoningBlock as ReasoningType } from "@/lib/types";
import { CheckCircle, XCircle, TrendingUp, ArrowRight } from "lucide-react";

type Props = { reasoning: ReasoningType };

export default function ReasoningBlock({ reasoning }: Props) {
  return (
    <div className="rounded-lg bg-surface-low/40 ghost-border p-4 space-y-3">
      <p className="text-xs font-semibold text-secondary uppercase tracking-wide">
        Why this, not that
      </p>

      <div className="flex items-start gap-2">
        <CheckCircle size={14} className="text-emerald-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-medium text-on-surface">Why this pick</p>
          <p className="text-xs text-on-surface-variant leading-relaxed">{reasoning.why_this}</p>
        </div>
      </div>

      <div className="flex items-start gap-2">
        <XCircle size={14} className="text-red-400 shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-medium text-on-surface">Why not {reasoning.second_best || "the alternative"}</p>
          <p className="text-xs text-on-surface-variant leading-relaxed">{reasoning.why_not_alt}</p>
        </div>
      </div>

      <div className="flex items-start gap-2">
        <TrendingUp size={14} className="text-primary shrink-0 mt-0.5" />
        <div>
          <p className="text-xs font-medium text-on-surface">Edge</p>
          <p className="text-xs text-on-surface-variant leading-relaxed">{reasoning.edge_summary}</p>
        </div>
      </div>

      {reasoning.confidence_gap && reasoning.confidence_gap !== "N/A" && (
        <div className="flex items-center gap-1 pt-1 border-t border-surface-container">
          <ArrowRight size={12} className="text-tertiary" />
          <span className="text-[10px] text-tertiary font-medium">{reasoning.confidence_gap}</span>
        </div>
      )}
    </div>
  );
}