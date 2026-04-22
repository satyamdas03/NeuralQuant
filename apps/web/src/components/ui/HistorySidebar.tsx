"use client";

type Props = {
  items: { id: string; preview: string; timestamp: string }[];
  activeId?: string;
  onSelect: (id: string) => void;
};

export default function HistorySidebar({
  items,
  activeId,
  onSelect,
}: Props) {
  return (
    <aside className="hidden w-56 shrink-0 flex-col gap-1 overflow-y-auto lg:flex">
      <p className="px-2 pb-2 text-xs font-semibold text-on-surface-variant">
        History
      </p>
      {items.map((item) => (
        <button
          key={item.id}
          onClick={() => onSelect(item.id)}
          className={`rounded-lg px-2 py-1.5 text-left text-xs transition-colors ${
            activeId === item.id
              ? "bg-surface-high text-on-surface"
              : "text-on-surface-variant hover:bg-surface-high hover:text-on-surface"
          }`}
        >
          <span className="line-clamp-2">{item.preview}</span>
          <span className="text-[10px] text-on-surface-variant">
            {item.timestamp}
          </span>
        </button>
      ))}
    </aside>
  );
}