import { Badge } from "@/components/ui/badge";
import type { RegimeLabel } from "@/lib/types";

const REGIME_STYLES: Record<RegimeLabel, string> = {
  "Risk-On":    "bg-green-500/10 text-green-400 border-green-500/20",
  "Recovery":   "bg-blue-500/10 text-blue-400 border-blue-500/20",
  "Late-Cycle": "bg-yellow-500/10 text-yellow-400 border-yellow-500/20",
  "Bear":       "bg-red-500/10 text-red-400 border-red-500/20",
};

export function RegimeBadge({ label }: { label: RegimeLabel }) {
  return (
    <Badge variant="outline" className={REGIME_STYLES[label]}>
      {label}
    </Badge>
  );
}
