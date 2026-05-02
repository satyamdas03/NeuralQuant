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
    "press-scale inline-flex items-center gap-2 rounded-xl font-semibold transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed glass-strong ghost-border text-on-surface hover:bg-surface-high hover:shadow-[0_0_24px_rgba(193,193,255,0.12)]";
  const sizes = size === "sm" ? "px-3 py-1.5 text-xs" : "px-5 py-2.5 text-sm";

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