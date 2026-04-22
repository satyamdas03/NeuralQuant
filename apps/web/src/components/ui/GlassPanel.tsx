type Props = {
  children: React.ReactNode;
  className?: string;
  strong?: boolean;
};

export default function GlassPanel({
  children,
  className = "",
  strong = false,
}: Props) {
  return (
    <div
      className={`rounded-2xl ${
        strong ? "glass-strong" : "glass"
      } ghost-border p-4 ${className}`}
    >
      {children}
    </div>
  );
}