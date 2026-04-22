"use client";

import { useState } from "react";
import { Send } from "lucide-react";

type Props = {
  onSubmit: (text: string) => void;
  placeholder?: string;
  disabled?: boolean;
};

export default function ChatInputArea({
  onSubmit,
  placeholder = "Ask about any stock...",
  disabled = false,
}: Props) {
  const [text, setText] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || disabled) return;
    onSubmit(text.trim());
    setText("");
  };

  return (
    <form onSubmit={handleSubmit} className="flex items-end gap-2">
      <div className="flex-1 rounded-xl bg-surface-high ghost-border px-4 py-3">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit(e);
            }
          }}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="w-full resize-none bg-transparent text-sm text-on-surface outline-none placeholder:text-on-surface-variant"
        />
      </div>
      <button
        type="submit"
        disabled={disabled || !text.trim()}
        className="gradient-cta press-scale flex h-10 w-10 items-center justify-center rounded-xl disabled:opacity-40"
      >
        <Send size={16} className="text-on-primary-container" />
      </button>
    </form>
  );
}