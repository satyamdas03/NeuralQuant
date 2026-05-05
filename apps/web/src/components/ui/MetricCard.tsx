import { cn } from "@/lib/utils";

interface MetricCardProps {
  label: string;
  value: string | number;
  accent?: "primary" | "secondary" | "tertiary" | "error" | "default";
  className?: string;
}

export default function MetricCard({ label, value, accent = "default", className }: MetricCardProps) {
  return (
    <div className={cn("rounded-xl ghost-border bg-surface-low/40 p-3", className)}>
      <p className="text-xs text-on-surface-variant">{label}</p>
      <p
        className={cn("font-headline text-lg font-bold", {
          "text-primary": accent === "primary",
          "text-secondary": accent === "secondary",
          "text-tertiary": accent === "tertiary",
          "text-red-400": accent === "error",
          "text-on-surface": accent === "default",
        })}
      >
        {value}
      </p>
    </div>
  );
}