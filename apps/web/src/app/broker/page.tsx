import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import BrokerPageClient from "./BrokerPageClient";

export default async function BrokerPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login?next=/broker");
  const tier = (user.app_metadata?.tier as string) || "free";
  return <BrokerPageClient email={user.email ?? ""} tier={tier} />;
}