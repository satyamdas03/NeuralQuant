"use client";

import { usePathname } from "next/navigation";
import SideNavBar from "./SideNavBar";
import BottomMobileNav from "./BottomMobileNav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";

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
