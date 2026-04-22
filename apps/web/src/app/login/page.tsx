"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import GradientButton from "@/components/ui/GradientButton";

export const dynamic = "force-dynamic";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const nextPath = params.get("next") || "/dashboard";
  const queryError = params.get("error");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(queryError);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      setError(error.message);
      return;
    }
    router.push(nextPath);
    router.refresh();
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm glass-strong ghost-border rounded-2xl p-8">
        <div className="mb-6 text-center">
          <h1 className="font-headline text-2xl font-bold text-on-surface">
            Sign in to NeuralQuant
          </h1>
          <p className="mt-1 text-xs text-on-surface-variant">
            Institutional-grade AI stock intelligence
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
            placeholder="password"
            className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface outline-none placeholder:text-on-surface-variant focus:ring-1 focus:ring-primary"
          />
          {error && <p className="text-sm text-error">{error}</p>}
          <GradientButton className="w-full justify-center">
            {loading ? "Signing in…" : "Sign in"}
          </GradientButton>
        </form>
        <p className="mt-4 text-center text-sm text-on-surface-variant">
          No account?{" "}
          <Link href="/signup" className="text-secondary hover:text-primary transition-colors">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}