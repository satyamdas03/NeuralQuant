// Public landing page. Authed users redirect to /dashboard.
import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import GradientButton from "@/components/ui/GradientButton";

export const dynamic = "force-dynamic";

export default async function Landing() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) redirect("/dashboard");

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(193,193,255,0.12),transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(189,244,255,0.08),transparent_60%)]" />
        <div className="relative max-w-6xl mx-auto px-6 pt-20 pb-24 md:pt-32 md:pb-36">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full ghost-border bg-primary/10 text-primary text-xs font-medium mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            AI stock intelligence for US + India
          </div>
          <h1 className="font-headline text-4xl md:text-6xl font-bold tracking-tight leading-[1.05]">
            Institutional-grade equity research.
            <br />
            <span className="gradient-cta bg-clip-text text-transparent">
              Powered by multi-agent AI.
            </span>
          </h1>
          <p className="mt-6 text-lg text-on-surface-variant max-w-2xl leading-relaxed">
            NeuralQuant fuses a 5-factor quant engine, regime detection, and a debate
            of specialist AI analysts into a single verdict per stock — across the
            S&amp;P 500 and NIFTY 500.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <GradientButton href="/signup" size="md">
              Get started free
            </GradientButton>
            <Link
              href="/login"
              className="px-6 py-2.5 rounded-xl ghost-border text-on-surface-variant hover:text-on-surface hover:bg-surface-high font-medium text-sm transition-colors"
            >
              Sign in
            </Link>
          </div>
          <div className="mt-10 flex flex-wrap gap-6 text-xs text-on-surface-variant">
            <span>✓ No credit card</span>
            <span>✓ 50 queries / day free</span>
            <span>✓ US + Indian markets</span>
          </div>
        </div>
      </section>

      {/* What it does */}
      <section className="max-w-6xl mx-auto px-6 py-20 border-t border-surface-container">
        <h2 className="font-headline text-3xl md:text-4xl font-bold tracking-tight mb-3">
          Stop guessing. Start debating.
        </h2>
        <p className="text-on-surface-variant max-w-2xl">
          Four independent AI analysts argue every thesis. You see the verdict,
          the dissent, and the numbers behind both.
        </p>
        <div className="grid md:grid-cols-2 gap-4 mt-10">
          <Feature
            title="PARA-DEBATE Engine"
            body="Bull, Bear, Skeptic, and Macro agents run in parallel on the same question. A Judge agent synthesizes the ruling with sources cited."
          />
          <Feature
            title="5-Factor Quant Core"
            body="Value, Momentum, Quality, Low-Vol, Short-Interest percentiles — computed nightly across 1000+ tickers with sector-adjusted ranking."
          />
          <Feature
            title="Regime Detection"
            body="HMM-driven bull/bear/choppy classification reweights factors dynamically. Momentum in uptrends, quality in drawdowns."
          />
          <Feature
            title="Portfolio Construction"
            body="Ask in plain English: '₹10L across Indian midcaps' or 'low-vol US dividend names.' Get a sized basket with return bands."
          />
          <Feature
            title="Watchlist + Alerts"
            body="Track tickers across US and India. Price, score, and thesis updates in one pane. Nightly recomputed."
          />
          <Feature
            title="Transparent Sources"
            body="Every answer cites the data it used — yfinance, FRED, SEC filings, analyst consensus. No black boxes."
          />
        </div>
      </section>

      {/* Universe */}
      <section className="max-w-6xl mx-auto px-6 py-20 border-t border-surface-container">
        <div className="grid md:grid-cols-3 gap-8">
          <Stat num="1000+" label="US + Indian tickers scored nightly" />
          <Stat num="5" label="ForeCast™ factors, sector-adjusted" />
          <Stat num="4" label="AI analysts debate every thesis" />
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-6 py-24 border-t border-surface-container">
        <div className="glass-strong ghost-border rounded-2xl p-10 md:p-14 text-center">
          <h2 className="font-headline text-3xl md:text-4xl font-bold tracking-tight">
            Ready to see the full engine?
          </h2>
          <p className="mt-3 text-on-surface-variant max-w-xl mx-auto">
            Create a free account — screener, watchlist, portfolio builder, and
            AI debate unlock instantly.
          </p>
          <GradientButton href="/signup" size="md" className="mt-8">
            Create free account
          </GradientButton>
        </div>
      </section>

      <footer className="max-w-6xl mx-auto px-6 py-10 text-xs text-on-surface-variant border-t border-surface-container">
        © {new Date().getFullYear()} NeuralQuant · Research tool, not investment advice.
      </footer>
    </div>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl ghost-border bg-surface-low/40 p-6 hover-glow transition-colors">
      <h3 className="font-semibold text-on-surface">{title}</h3>
      <p className="mt-2 text-sm text-on-surface-variant leading-relaxed">{body}</p>
    </div>
  );
}

function Stat({ num, label }: { num: string; label: string }) {
  return (
    <div>
      <div className="font-headline text-4xl font-bold gradient-cta bg-clip-text text-transparent">
        {num}
      </div>
      <div className="mt-2 text-sm text-on-surface-variant">{label}</div>
    </div>
  );
}