"use client";

import { useEffect, useState, useCallback } from "react";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";
import SideNavBar from "./SideNavBar";
import BottomMobileNav from "./BottomMobileNav";
import MobileDrawer from "./MobileDrawer";
import { useSessionTracker } from "@/lib/session-tracker";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";
  const [drawerOpen, setDrawerOpen] = useState(false);
  const { logActivity } = useSessionTracker();

  const openDrawer = useCallback(() => setDrawerOpen(true), []);
  const closeDrawer = useCallback(() => setDrawerOpen(false), []);

  // Log page views on navigation
  useEffect(() => {
    if (!isLanding) {
      logActivity("page_view", "navigation", `Visited ${pathname}`, {
        path: pathname,
        title: typeof document !== "undefined" ? document.title : "",
      });
    }
  }, [pathname, isLanding, logActivity]);

  if (isLanding) {
    return <>{children}</>;
  }

  return (
    <div className="relative min-h-screen overflow-x-hidden">
      {/* Grid overlay */}
      <div className="fixed inset-0 z-0 pointer-events-none grid-overlay" />
      {/* Scanline overlay */}
      <div className="fixed inset-0 z-0 pointer-events-none scanline-overlay" />

      {/* Hamburger — mobile only */}
      <button
        onClick={openDrawer}
        className="fixed top-4 left-4 z-40 lg:hidden flex items-center justify-center w-10 h-10 glass border border-border-glow text-primary-fixed"
        aria-label="Open navigation menu"
      >
        <Menu size={20} />
      </button>

      <SideNavBar />
      <MobileDrawer open={drawerOpen} onClose={closeDrawer} />

      <main className="relative z-10 pb-20 lg:ml-[280px] lg:pb-0">
        {children}
      </main>
      <BottomMobileNav onOpenDrawer={openDrawer} />
    </div>
  );
}
