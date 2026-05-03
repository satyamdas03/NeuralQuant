"use client";

import { usePathname } from "next/navigation";
import SideNavBar from "./SideNavBar";
import BottomMobileNav from "./BottomMobileNav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";

  return (
    <>
      {!isLanding && <SideNavBar />}
      <main className={isLanding ? "" : "pb-20 lg:pl-64 lg:pb-0"}>{children}</main>
      {!isLanding && <BottomMobileNav />}
    </>
  );
}