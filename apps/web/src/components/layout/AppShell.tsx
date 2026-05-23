"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import SideNavBar from "./SideNavBar";
import BottomMobileNav from "./BottomMobileNav";
import { useSessionTracker } from "@/lib/session-tracker";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";
  const { logActivity } = useSessionTracker();

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
    <div className="relative min-h-screen">
      {/* Grid overlay */}
      <div className="fixed inset-0 z-0 pointer-events-none grid-overlay" />
      {/* Scanline overlay */}
      <div className="fixed inset-0 z-0 pointer-events-none scanline-overlay" />
      <SideNavBar />
      <main className="relative z-10 pb-20 lg:ml-[280px] lg:pb-0">
        {children}
      </main>
      <BottomMobileNav />
    </div>
  );
}
