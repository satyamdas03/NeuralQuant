import type { ReasoningBlock as ReasoningType } from "@/lib/types";
import { CheckCircle, XCircle, TrendingUp, ArrowRight } from "lucide-react";

type Props = { reasoning: ReasoningType };

function _isPlaceholder(val: string | undefined): boolean {
  if (!val) return true;
  const v = val.trim().toLowerCase();
  return v === "n/a" || v === "na" || v === "" || v.length < 3;
}

export default function ReasoningBlock({ reasoning }: Props) {
  const hasWhy = !_isPlaceholder(reasoning.why_this);
  const hasAlt = !_isPlaceholder(reasoning.why_not_alt);
  const hasEdge = !_isPlaceholder(reasoning.edge_summary);
  const hasGap = !_isPlaceholder(reasoning.confidence_gap);

  if (!hasWhy && !hasAlt && !hasEdge && !hasGap) return null;

  return (
    <div className="rounded-lg bg-surface-low/40 ghost-border p-4 space-y-3">
      <p className="text-xs font-semibold text-secondary uppercase tracking-wide">
        Why this, not that
      </p>

      {hasWhy && (
        <div className="flex items-start gap-2">
          <CheckCircle size={14} className="text-emerald-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-on-surface">Why this pick</p>
            <p className="text-xs text-on-surface-variant leading-relaxed">{reasoning.why_this}</p>
          </div>
        </div>
      )}

      {hasAlt && (
        <div className="flex items-start gap-2">
          <XCircle size={14} className="text-red-400 shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-on-surface">Why not {_isPlaceholder(reasoning.second_best) ? "the alternative" : reasoning.second_best}</p>
            <p className="text-xs text-on-surface-variant leading-relaxed">{reasoning.why_not_alt}</p>
          </div>
        </div>
      )}

      {hasEdge && (
        <div className="flex items-start gap-2">
          <TrendingUp size={14} className="text-primary shrink-0 mt-0.5" />
          <div>
            <p className="text-xs font-medium text-on-surface">Edge</p>
            <p className="text-xs text-on-surface-variant leading-relaxed">{reasoning.edge_summary}</p>
          </div>
        </div>
      )}

      {hasGap && (
        <div className="flex items-center gap-1 pt-1 border-t border-surface-container">
          <ArrowRight size={12} className="text-tertiary" />
          <span className="text-[10px] text-tertiary font-medium">{reasoning.confidence_gap}</span>
        </div>
      )}
    </div>
  );
}