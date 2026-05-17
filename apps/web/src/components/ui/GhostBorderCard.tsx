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
      className={`glass border border-border-glow p-4 ${
        hover ? "hover:shadow-[0_0_20px_rgba(0,255,178,0.15)] hover:border-primary-fixed/40 cursor-pointer transition-all duration-300" : ""
      } ${className}`}
    >
      {children}
    </div>
  );
}
