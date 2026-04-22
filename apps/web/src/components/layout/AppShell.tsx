import SideNavBar from "./SideNavBar";
import TopNavBar from "./TopNavBar";
import BottomMobileNav from "./BottomMobileNav";

export default function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SideNavBar />
      <TopNavBar />
      <main className="pt-14 pb-20 lg:pl-64 lg:pb-0">{children}</main>
      <BottomMobileNav />
    </>
  );
}