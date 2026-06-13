"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import GradientButton from "@/components/ui/GradientButton";
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { trackEvent, EVENT, analytics } from "@/lib/analytics";

function SignupForm() {
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
    trackEvent(EVENT.AUTH_STARTED, { provider: "email_signup" });
    const supabase = createClient();
    const refCode = searchParams.get("ref");
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: refCode ? { referral_code: refCode } : undefined,
        emailRedirectTo: (() => {
          const envUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim();
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
    // Fire-and-forget welcome email (backup for Supabase DB trigger)
    if (data.session || data.user) {
      // Track signup completion
      const method = "email";
      analytics.signupCompleted(method).catch(() => {});
      // If came from a shared analysis, track signup_from_share
      const shareId = searchParams.get("from_share");
      if (shareId) {
        analytics.signupFromShare(shareId).catch(() => {});
      }
      fetch("/api/auth/welcome", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, name: email.split("@")[0] }),
      }).catch(() => {/* best-effort */});
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
      <div className="w-full max-w-sm glass-strong ghost-border p-8">
        <div className="mb-6 text-center">
          <h1 className="font-headline text-2xl font-bold text-primary-fixed">
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
            className="w-full bg-surface-high px-3 py-2 text-sm text-on-surface outline-none placeholder:text-on-surface-variant focus:ring-1 focus:ring-primary-fixed"
          />
          <input
            type="password"
            required
            minLength={6}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="password (min 6 chars)"
            className="w-full bg-surface-high px-3 py-2 text-sm text-on-surface outline-none placeholder:text-on-surface-variant focus:ring-1 focus:ring-primary-fixed"
          />
          {error && <p className="text-sm text-error">{error}</p>}
          {info && <p className="text-sm text-tertiary-fixed-dim">{info}</p>}
          <GoogleSignInButton label="Sign up with Google" />
          <div className="flex items-center gap-2 text-xs text-on-surface-variant">
            <span className="h-px flex-1 bg-ghost-border" />
            <span>or</span>
            <span className="h-px flex-1 bg-ghost-border" />
          </div>
          <GradientButton className="w-full justify-center">
            {loading ? "Creating…" : "Create account"}
          </GradientButton>
        </form>
        <p className="mt-4 text-center text-sm text-on-surface-variant">
          Already have one?{" "}
          <Link href="/login" className="text-primary-fixed hover:text-primary transition-colors">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}