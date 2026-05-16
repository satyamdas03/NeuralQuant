type Props = {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  id?: string;
};

export default function GhostBorderCard({
  children,
  className = "",
  hover = false,
  id,
}: Props) {
  return (
    <div
      id={id}
      className={`rounded-xl bg-surface-container ghost-border p-4 ${
        hover ? "hover-glow cursor-pointer" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}