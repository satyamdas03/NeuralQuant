"use client";

import { usePathname } from "next/navigation";
import { Search, Bell, Wallet } from "lucide-react";
import { useState } from "react";

const PAGE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/news": "NewsDesk",
  "/screener": "AI Screener",
  "/query": "Ask AI",
  "/backtest": "Strategy Backtest",
  "/smart-money": "Smart Money Tracker",
  "/watchlist": "Watchlist",
  "/stocks": "Stock Detail",
  "/login": "Sign In",
  "/signup": "Sign Up",
};

export default function TopNavBar() {
  const pathname = usePathname();
  const [searchOpen, setSearchOpen] = useState(false);

  const title =
    PAGE_TITLES[pathname] ??
    (pathname.startsWith("/stocks") ? "Stock Detail" : "NeuralQuant");

  return (
    <header className="fixed inset-x-0 top-0 z-20 glass border-b border-ghost-border lg:left-64">
      <div className="flex h-14 items-center justify-between px-4 lg:px-6">
        <h1 className="font-headline text-base font-semibold text-on-surface">
          {title}
        </h1>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setSearchOpen(!searchOpen)}
            className="hidden sm:flex items-center gap-2 rounded-lg bg-surface-high px-3 py-1.5 text-xs text-on-surface-variant hover:bg-surface-highest transition-colors"
          >
            <Search size={14} />
            <span>Search&hellip;</span>
            <kbd className="ml-2 rounded bg-surface-highest px-1.5 py-0.5 text-[10px] text-on-surface-variant">
              ⌘K
            </kbd>
          </button>

          <button
            aria-label="Notifications"
            className="rounded-lg p-2 text-on-surface-variant hover:bg-surface-high transition-colors"
          >
            <Bell size={18} />
          </button>

          <button
            aria-label="Wallet"
            className="rounded-lg p-2 text-on-surface-variant hover:bg-surface-high transition-colors"
          >
            <Wallet size={18} />
          </button>
        </div>
      </div>

      {searchOpen && (
        <div className="border-t border-ghost-border px-4 py-2 sm:hidden">
          <div className="flex items-center gap-2 rounded-lg bg-surface-high px-3 py-2">
            <Search size={14} className="text-on-surface-variant" />
            <input
              autoFocus
              placeholder="Search ticker or company..."
              className="flex-1 bg-transparent text-sm text-on-surface outline-none placeholder:text-on-surface-variant"
            />
          </div>
        </div>
      )}
    </header>
  );
}