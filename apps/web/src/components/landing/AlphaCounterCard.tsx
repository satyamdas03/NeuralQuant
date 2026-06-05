"use client";

import { useEffect, useRef, useState } from "react";

interface AlphaCounterCardProps {
  label: string;
  value: number;
  suffix?: string;
  prefix?: string;
  color?: "positive" | "neutral" | "negative";
  animate?: boolean;
  subtext?: string;
}

const COLOR_MAP = {
  positive: "var(--color-primary)",
  neutral: "var(--color-text-muted)",
  negative: "var(--color-cyber-red)",
};

export default function AlphaCounterCard({
  label,
  value,
  suffix = "",
  prefix = "",
  color = "positive",
  animate = false,
  subtext,
}: AlphaCounterCardProps) {
  const [displayValue, setDisplayValue] = useState(0);
  const rafRef = useRef<number | null>(null);
  const startTimeRef = useRef<number | null>(null);
  const hasAnimated = useRef(false);

  const duration = 1500;

  useEffect(() => {
    if (!animate || hasAnimated.current) return;
    hasAnimated.current = true;

    const start = 0;
    const end = value;

    const tick = (timestamp: number) => {
      if (startTimeRef.current === null) {
        startTimeRef.current = timestamp;
      }

      const elapsed = timestamp - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);

      // easeOutQuart
      const eased = 1 - Math.pow(1 - progress, 4);
      const current = start + (end - start) * eased;

      setDisplayValue(current);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [animate, value]);

  const formatted =
    value % 1 !== 0
      ? displayValue.toFixed(1)
      : Math.round(displayValue).toString();

  const colorValue = COLOR_MAP[color];

  return (
    <div
      className="relative flex flex-col items-center justify-center p-6 md:p-8 border"
      style={{
        background: "rgba(13, 20, 37, 0.7)",
        backdropFilter: "blur(8px)",
        WebkitBackdropFilter: "blur(8px)",
        borderColor: "rgba(0, 255, 178, 0.15)",
      }}
    >
      {/* Top accent line */}
      <div
        className="absolute top-0 left-0 right-0 h-[2px]"
        style={{ background: colorValue }}
      />

      <span className="font-mono text-[10px] font-bold tracking-[0.2em] uppercase text-text-muted mb-3">
        {label}
      </span>

      <div className="font-headline text-4xl md:text-5xl font-bold tabular-nums tracking-tight"
        style={{ color: colorValue }}
      >
        {prefix}
        {formatted}
        {suffix}
      </div>

      {subtext && (
        <span className="mt-2 font-mono text-[10px] text-text-muted tracking-wide">
          {subtext}
        </span>
      )}
    </div>
  );
}
