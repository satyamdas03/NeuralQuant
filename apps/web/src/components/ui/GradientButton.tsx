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
    "gradient-cta gradient-cta-shadow press-scale inline-flex items-center gap-2 rounded-xl font-semibold text-on-primary-container transition-shadow hover:shadow-lg disabled:opacity-50 disabled:cursor-not-allowed";
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