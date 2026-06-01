"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  ScanSearch,
  MessageSquareText,
  FlaskConical,
  Star,
  Bell,
  Newspaper,
  LogIn,
  Terminal,
  TrendingUp,
} from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Workspace", icon: LayoutDashboard },
  { href: "/news", label: "NewsDesk", icon: Newspaper },
  { href: "/screener", label: "Screener", icon: ScanSearch },
  { href: "/query", label: "Ask Morgan", icon: MessageSquareText },
  { href: "/backtest", label: "Strategy", icon: FlaskConical },
  { href: "/trade", label: "Trade", icon: TrendingUp, beta: true },
  { href: "/terminal", label: "Terminal", icon: Terminal, beta: true },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/alerts", label: "Alerts", icon: Bell },
];

export default function SideNavBar() {
  const pathname = usePathname();

  return (
    <aside
      id="sidebar-nav"
      className="fixed left-0 top-0 h-full w-[280px] hidden lg:flex flex-col bg-surface-container-lowest border-r border-border-glow py-8 gap-2 z-50"
    >
      <div className="px-6 mb-8 flex flex-col gap-2">
        <span className="font-mono text-[11px] font-bold tracking-[0.2em] text-primary-fixed uppercase">
          QuantAlpha
        </span>
        <span className="font-mono text-[12px] text-text-muted">
          V2.0.4-BETA
        </span>
      </div>

      <nav className="flex-1 flex flex-col gap-1 px-0">
        {NAV.map(({ href, label, icon: Icon, beta }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-4 px-6 py-4 transition-all duration-200 group relative overflow-hidden ${
                active
                  ? "bg-primary-fixed/10 text-primary-fixed border-l-4 border-primary-fixed"
                  : "text-text-muted hover:bg-surface-container-low hover:text-primary border-l-4 border-transparent"
              }`}
            >
              <Icon size={18} />
              <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase">
                {label}
              </span>
              {beta && (
                <span className="text-[9px] font-medium px-1 py-0.5 bg-amber-500/15 text-amber-400 border border-amber-500/25 leading-none font-mono">
                  BETA
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="px-6 mt-auto flex flex-col gap-4">
        <Link
          href="/query"
          className="bg-primary-fixed text-background font-mono text-[12px] px-4 py-3 hover:shadow-[0_0_20px_rgba(0,255,178,0.3)] transition-all duration-300 w-full text-center font-bold tracking-[0.1em] uppercase"
        >
          New Research
        </Link>
        <div className="flex flex-col gap-1">
          <a
            href="#"
            className="flex items-center gap-4 text-text-muted px-0 py-2 hover:text-primary transition-all duration-200"
          >
            <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase">
              Documentation
            </span>
          </a>
          <a
            href="#"
            className="flex items-center gap-4 text-text-muted px-0 py-2 hover:text-primary transition-all duration-200"
          >
            <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase">
              Support
            </span>
          </a>
        </div>
        <Link
          href="/login"
          className="flex items-center gap-4 text-text-muted px-0 py-2 hover:text-primary transition-all duration-200"
        >
          <LogIn size={16} />
          <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase">
            Sign In
          </span>
        </Link>
      </div>
    </aside>
  );
}
