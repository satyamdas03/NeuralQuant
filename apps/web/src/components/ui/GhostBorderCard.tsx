type Props = {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
};

export default function GhostBorderCard({
  children,
  className = "",
  hover = false,
}: Props) {
  return (
    <div
      className={`rounded-xl bg-surface-container ghost-border p-4 ${
        hover ? "hover-glow cursor-pointer" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}