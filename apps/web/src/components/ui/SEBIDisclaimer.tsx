"use client";

export default function SEBIDisclaimer({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-3 py-2">
      <p className="text-[10px] leading-relaxed text-amber-200/80">
        {text}
      </p>
    </div>
  );
}
