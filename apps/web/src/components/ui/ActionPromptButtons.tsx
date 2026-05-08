"use client";

import type { ActionPrompt } from "@/lib/types";

export default function ActionPromptButtons({
  prompts,
  onPromptClick,
}: {
  prompts: ActionPrompt[];
  onPromptClick: (text: string) => void;
}) {
  if (!prompts || prompts.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {prompts.map((p, i) => (
        <button
          key={i}
          onClick={() => onPromptClick(p.prompt_text)}
          className="rounded-full bg-primary/10 border border-primary/20 px-3 py-1.5 text-xs font-medium text-primary hover:bg-primary/20 transition-colors"
        >
          {p.icon && <span className="mr-1">{p.icon}</span>}
          {p.label}
        </button>
      ))}
    </div>
  );
}
