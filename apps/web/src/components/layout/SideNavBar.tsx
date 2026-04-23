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
  Briefcase,
  Newspaper,
  LogIn,
} from "lucide-react";
import GradientButton from "@/components/ui/GradientButton";

const NAV = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/news", label: "NewsDesk", icon: Newspaper },
  { href: "/screener", label: "Screener", icon: ScanSearch },
  { href: "/query", label: "Ask AI", icon: MessageSquareText },
  { href: "/backtest", label: "Backtest", icon: FlaskConical },
  { href: "/smart-money", label: "Smart Money", icon: Briefcase },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/alerts", label: "Alerts", icon: Bell },
];

export default function SideNavBar() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col bg-surface-lowest border-r border-ghost-border lg:flex">
      <div className="flex h-16 items-center gap-2 px-6">
        <span className="font-headline text-lg font-bold tracking-tight text-primary">
          NeuralQuant
        </span>
      </div>

      <div className="px-4 pb-4">
        <GradientButton href="/dashboard" className="w-full justify-center">
          Open Dashboard
        </GradientButton>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors ${
                active
                  ? "bg-surface-high text-on-surface font-medium"
                  : "text-on-surface-variant hover:bg-surface-high hover:text-on-surface"
              }`}
            >
              <Icon size={18} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-ghost-border px-3 py-4">
        <Link
          href="/login"
          className="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-on-surface-variant hover:bg-surface-high hover:text-on-surface transition-colors"
        >
          <LogIn size={18} />
          Sign In
        </Link>
      </div>
    </aside>
  );
}
