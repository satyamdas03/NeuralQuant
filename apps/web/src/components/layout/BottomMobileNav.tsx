"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ScanSearch,
  MessageSquareText,
  Newspaper,
  TrendingUp,
  Menu,
} from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Workspace", icon: LayoutDashboard },
  { href: "/news", label: "News", icon: Newspaper },
  { href: "/screener", label: "Screener", icon: ScanSearch },
  { href: "/query", label: "Ask Morgan", icon: MessageSquareText, center: true },
  { href: "/trade", label: "Trade", icon: TrendingUp, beta: true },
];

export default function BottomMobileNav({ onOpenDrawer }: { onOpenDrawer: () => void }) {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 glass border-t border-border-glow lg:hidden safe-area-pb">
      <div className="flex h-16 items-center justify-around">
        {NAV.map(({ href, label, icon: Icon, center, beta }) => {
          const active = pathname.startsWith(href);

          if (center) {
            return (
              <Link
                key={href}
                href={href}
                className="bg-primary-fixed text-background -mt-6 flex h-14 w-14 items-center justify-center rounded-full shadow-[0_0_30px_rgba(0,255,178,0.3)]"
              >
                <Icon size={22} />
              </Link>
            );
          }

          return (
            <Link
              key={href}
              href={href}
              className="flex flex-col items-center gap-0.5"
            >
              <Icon
                size={18}
                className={active ? "text-primary-fixed" : "text-text-muted"}
              />
              <span
                className={`font-mono text-[10px] flex items-center gap-0.5 uppercase tracking-wider ${
                  active ? "text-primary-fixed" : "text-text-muted"
                }`}
              >
                {label}
                {beta && (
                  <span className="text-[7px] font-medium px-0.5 bg-amber-500/15 text-amber-400 border border-amber-500/25 leading-none">
                    BETA
                  </span>
                )}
              </span>
            </Link>
          );
        })}

        {/* More — opens mobile drawer */}
        <button
          onClick={onOpenDrawer}
          className="flex flex-col items-center gap-0.5"
          aria-label="More navigation options"
        >
          <Menu size={18} className="text-text-muted" />
          <span className="font-mono text-[10px] uppercase tracking-wider text-text-muted">
            More
          </span>
        </button>
      </div>
    </nav>
  );
}
