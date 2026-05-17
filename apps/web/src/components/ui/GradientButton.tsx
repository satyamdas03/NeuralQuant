import Link from "next/link";

type Props = {
  children: React.ReactNode;
  href?: string;
  onClick?: () => void;
  className?: string;
  size?: "sm" | "md";
  disabled?: boolean;
  type?: "button" | "submit";
};

export default function GradientButton({
  children,
  href,
  onClick,
  className = "",
  size = "md",
  disabled,
  type,
}: Props) {
  const base =
    "press-scale inline-flex items-center gap-2 font-mono font-bold tracking-[0.1em] uppercase transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed glass border border-border-glow text-primary hover:bg-surface-container-high hover:shadow-[0_0_20px_rgba(0,255,178,0.15)] hover:border-primary-fixed/40";
  const sizes = size === "sm" ? "px-3 py-1.5 text-[11px]" : "px-5 py-2.5 text-[12px]";

  if (href) {
    return (
      <Link href={href} className={`${base} ${sizes} ${className}`} aria-disabled={disabled}>
        {children}
      </Link>
    );
  }

  return (
    <button onClick={onClick} className={`${base} ${sizes} ${className}`} disabled={disabled} type={type}>
      {children}
    </button>
  );
}
