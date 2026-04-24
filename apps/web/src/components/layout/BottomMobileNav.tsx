"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ScanSearch,
  MessageSquareText,
  FlaskConical,
  Briefcase,
  Newspaper,
  Star,
  Database,
  GitCompareArrows,
} from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/news", label: "NewsDesk", icon: Newspaper },
  { href: "/screener", label: "Screener", icon: ScanSearch },
  { href: "/query", label: "Ask AI", icon: MessageSquareText, center: true },
  { href: "/sources", label: "Sources", icon: Database },
  { href: "/compare", label: "Compare", icon: GitCompareArrows },
  { href: "/smart-money", label: "Smart Money", icon: Briefcase },
  { href: "/watchlist", label: "Watchlist", icon: Star },
];

export default function BottomMobileNav() {
  const pathname = usePathname();

  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 glass border-t border-ghost-border lg:hidden safe-area-pb">
      <div className="flex h-16 items-center justify-around">
        {NAV.map(({ href, label, icon: Icon, center }) => {
          const active = pathname.startsWith(href);

          if (center) {
            return (
              <Link
                key={href}
                href={href}
                className="gradient-cta -mt-6 flex h-14 w-14 items-center justify-center rounded-full gradient-cta-shadow"
              >
                <Icon size={22} className="text-on-primary-container" />
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
                className={active ? "text-primary" : "text-on-surface-variant"}
              />
              <span
                className={`text-[10px] ${
                  active ? "text-primary" : "text-on-surface-variant"
                }`}
              >
                {label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}