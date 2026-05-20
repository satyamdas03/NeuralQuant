"use client";

import { RefObject } from "react";

interface TranscriptLine {
  text: string;
  source: "agent" | "user";
  final: boolean;
  timestamp: number;
}

export default function QuantAstraTranscriptPanel({
  lines,
  endRef,
}: {
  lines: TranscriptLine[];
  endRef: RefObject<HTMLDivElement | null>;
}) {
  if (lines.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-4">
        <p className="text-xs text-on-surface-variant/60">
          Transcript will appear here...
        </p>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-3 space-y-2">
      {lines.map((line, i) => (
        <div
          key={`${line.timestamp}-${i}`}
          className={`flex ${line.source === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-[85%] rounded-lg px-3 py-1.5 text-xs leading-relaxed ${
              line.source === "user"
                ? "bg-primary-fixed/10 text-on-surface"
                : "bg-surface-high/80 text-on-surface"
            } ${!line.final && line.source === "agent" ? "border-l-2 border-primary-fixed animate-pulse" : ""}`}
          >
            {line.source === "agent" && (
              <span className="mr-1.5 text-[10px] font-semibold text-primary-fixed">
                QuantAstra
              </span>
            )}
            {line.source === "user" && (
              <span className="mr-1.5 text-[10px] font-semibold text-sky-400">
                You
              </span>
            )}
            <span className={line.source === "agent" && !line.final ? "italic" : ""}>
              {line.text}
            </span>
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}
