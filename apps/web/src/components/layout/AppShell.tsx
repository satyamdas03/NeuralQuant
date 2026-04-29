"use client";

import { usePathname } from "next/navigation";
import SideNavBar from "./SideNavBar";
import TopNavBar from "./TopNavBar";
import BottomMobileNav from "./BottomMobileNav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isLanding = pathname === "/";

  return (
    <>
      {!isLanding && <SideNavBar />}
      {!isLanding && <TopNavBar />}
      <main className={isLanding ? "" : "pt-14 pb-20 lg:pl-64 lg:pb-0"}>{children}</main>
      {!isLanding && <BottomMobileNav />}
    </>
  );
}