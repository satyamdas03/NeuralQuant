"use client";

type Props = {
  suggestions: string[];
  onSelect: (text: string) => void;
};

export default function SuggestionChips({ suggestions, onSelect }: Props) {
  return (
    <div className="flex flex-wrap gap-2">
      {suggestions.map((s) => (
        <button
          key={s}
          onClick={() => onSelect(s)}
          className="rounded-full bg-surface-high px-3 py-1 text-xs text-on-surface-variant hover:bg-surface-highest hover:text-on-surface transition-colors"
        >
          {s}
        </button>
      ))}
    </div>
  );
}