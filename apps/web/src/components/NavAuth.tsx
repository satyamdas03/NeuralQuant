"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";

export default function NavAuth() {
  const [email, setEmail] = useState<string | null>(null);

  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? null));
    const { data: sub } = supabase.auth.onAuthStateChange((_evt, session) => {
      setEmail(session?.user.email ?? null);
    });
    return () => sub.subscription.unsubscribe();
  }, []);

  if (!email) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <Link href="/login" className="text-white/70 hover:text-white">Sign in</Link>
        <Link
          href="/signup"
          className="rounded-md bg-emerald-500 px-3 py-1.5 font-medium text-black hover:bg-emerald-400"
        >
          Sign up
        </Link>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-3 text-sm">
      <Link href="/watchlist" className="text-white/70 hover:text-white">
        Watchlist
      </Link>
      <span className="text-white/40">{email}</span>
      <form action="/auth/sign-out" method="POST">
        <button className="text-white/60 hover:text-white">Sign out</button>
      </form>
    </div>
  );
}
