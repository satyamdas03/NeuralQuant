"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import GradientButton from "@/components/ui/GradientButton";

export default function SignupPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setLoading(true);
    const supabase = createClient();
    const refCode = searchParams.get("ref");
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: refCode ? { referral_code: refCode } : undefined,
        emailRedirectTo: (() => {
          const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
          const base =
            envUrl ||
            (typeof window !== "undefined" ? window.location.origin : "");
          return base ? `${base}/auth/callback` : undefined;
        })(),
      },
    });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    if (data.session) {
      router.push("/dashboard");
      router.refresh();
    } else {
      setInfo("Check your inbox to confirm your email.");
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm glass-strong ghost-border rounded-2xl p-8">
        <div className="mb-6 text-center">
          <h1 className="font-headline text-2xl font-bold text-on-surface">
            Create your account
          </h1>
          <p className="mt-1 text-xs text-on-surface-variant">
            Join NeuralQuant — AI stock intelligence
          </p>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface outline-none placeholder:text-on-surface-variant focus:ring-1 focus:ring-primary"
          />
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="password (min 6 chars)"
            className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface outline-none placeholder:text-on-surface-variant focus:ring-1 focus:ring-primary"
          />
          {error && <p className="text-sm text-error">{error}</p>}
          {info && <p className="text-sm text-tertiary">{info}</p>}
          <GradientButton className="w-full justify-center">
            {loading ? "Creating…" : "Create account"}
          </GradientButton>
        </form>
        <p className="mt-4 text-center text-sm text-on-surface-variant">
          Already have one?{" "}
          <Link href="/login" className="text-secondary hover:text-primary transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}