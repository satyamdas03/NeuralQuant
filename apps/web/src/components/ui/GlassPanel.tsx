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
      className={`${
        strong ? "glass-strong" : "glass"
      } ghost-border p-4 ${className}`}
    >
      {children}
    </div>
  );
}
