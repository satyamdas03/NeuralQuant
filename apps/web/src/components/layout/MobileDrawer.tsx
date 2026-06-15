"use client";

import { useEffect, useCallback, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import {
  LayoutDashboard,
  ScanSearch,
  MessageSquareText,
  Star,
  Bell,
  Newspaper,
  LogIn,
  LogOut,
  X,
  Bot,
} from "lucide-react";

const NAV = [
  { href: "/dashboard", label: "Workspace", icon: LayoutDashboard },
  { href: "/news", label: "NewsDesk", icon: Newspaper },
  { href: "/screener", label: "Screener", icon: ScanSearch },
  { href: "/query", label: "Ask Morgan", icon: MessageSquareText },
  { href: "/hermes", label: "Live Trading", icon: Bot, beta: true },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/alerts", label: "Alerts", icon: Bell },
];

interface MobileDrawerProps {
  open: boolean;
  onClose: () => void;
}

export default function MobileDrawer({ open, onClose }: MobileDrawerProps) {
  const pathname = usePathname();
  const router = useRouter();
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    const { data: sub } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user?.email ?? null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  const handleSignOut = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    setEmail(null);
    onClose();
    router.push("/login");
    router.refresh();
  };

  // Close on Escape key
  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (open) {
      document.addEventListener("keydown", onKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onKeyDown]);

  // Close on route change
  useEffect(() => {
    onClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer panel */}
      <aside className="absolute left-0 top-0 h-full w-[280px] bg-surface-lowest border-r border-border-glow flex flex-col py-8 gap-2 safe-area-pt animate-slide-in-left z-10">
        {/* Header */}
        <div className="px-6 mb-6 flex items-center justify-between">
          <div className="flex flex-col gap-2">
            <span className="font-mono text-[11px] font-bold tracking-[0.2em] text-primary-fixed uppercase">
              NeuralQuant
            </span>
            <span className="font-mono text-[12px] text-text-muted">
              V2.0.4-BETA
            </span>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-high transition-colors"
            aria-label="Close menu"
          >
            <X size={20} />
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 flex flex-col gap-1 overflow-y-auto">
          {NAV.map(({ href, label, icon: Icon, ...rest }) => {
            const beta = (rest as Record<string, unknown>).beta as boolean | undefined;
            const active = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                onClick={onClose}
                className={`flex items-center gap-4 px-6 py-4 transition-all duration-200 ${
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

        {/* Bottom links */}
        <div className="px-6 mt-auto flex flex-col gap-4 safe-area-pb">
          <Link
            href="/query"
            onClick={onClose}
            className="bg-primary-fixed text-background font-mono text-[12px] px-4 py-3 hover:shadow-[0_0_20px_rgba(0,255,178,0.3)] transition-all duration-300 w-full text-center font-bold tracking-[0.1em] uppercase"
          >
            New Research
          </Link>
          {email ? (
            <button
              onClick={handleSignOut}
              title={email}
              className="flex items-center gap-4 text-text-muted px-0 py-2 hover:text-primary transition-all duration-200 text-left"
            >
              <LogOut size={16} />
              <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase truncate">
                Sign Out
              </span>
            </button>
          ) : (
            <Link
              href="/login"
              onClick={onClose}
              className="flex items-center gap-4 text-text-muted px-0 py-2 hover:text-primary transition-all duration-200"
            >
              <LogIn size={16} />
              <span className="font-mono text-[11px] font-bold tracking-[0.2em] uppercase">
                Sign In
              </span>
            </Link>
          )}
        </div>
      </aside>
    </div>
  );
}
