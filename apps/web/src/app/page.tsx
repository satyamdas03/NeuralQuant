// Public landing page. Authed users redirect to /dashboard.
import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import GradientButton from "@/components/ui/GradientButton";
import CitationCard from "@/components/ui/CitationCard";
import DebateShowcase from "@/components/ui/DebateShowcase";

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

      {/* PARA-DEBATE Showcase */}
      <section className="max-w-6xl mx-auto px-6 py-20 border-t border-surface-container">
        <div className="text-center mb-10">
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-tertiary/10 text-tertiary text-xs font-medium mb-4">
            PARA-DEBATE™
          </span>
          <h2 className="font-headline text-3xl md:text-4xl font-bold tracking-tight mb-3">
            AI analysts debate your stock.
          </h2>
          <p className="text-on-surface-variant max-w-2xl mx-auto">
            Before you invest, specialist agents argue every angle — macro, fundamentals,
            technicals, sentiment, geopolitics, and an adversarial devil&apos;s advocate —
            then a Bull vs. Bear debate settles it. A Head Analyst delivers the final verdict.
          </p>
        </div>
        <DebateShowcase />
        <div className="mt-8 text-center">
          <GradientButton href="/query" size="md">
            Watch them debate →
          </GradientButton>
        </div>
      </section>

      {/* Built on Published Research */}
      <section className="max-w-6xl mx-auto px-6 py-20 border-t border-surface-container">
        <h2 className="font-headline text-3xl md:text-4xl font-bold tracking-tight mb-3">
          Built on published research
        </h2>
        <p className="text-on-surface-variant max-w-2xl mb-10">
          Every NeuralQuant factor is grounded in peer-reviewed finance research —
          not hype.
        </p>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          <CitationCard
            title="Returns to Buying Winners and Selling Losers"
            authors="Jegadeesh & Titman"
            year={1993}
            application="Momentum factor — 12-1 month return ranking"
          />
          <CitationCard
            title="Value Investing: The Use of Historical Financial Statement Information"
            authors="Piotroski"
            year={2000}
            application="F-Score quality metric in our quality factor"
          />
          <CitationCard
            title="A New Approach to Filtering and Smoothing"
            authors="Hamilton"
            year={1989}
            application="Regime-switching HMM for bull/bear classification"
          />
          <CitationCard
            title="Contrarian Investment, Extrapolation, and Risk"
            authors="Lakonishok, Shleifer & Vishny"
            year={1994}
            application="Value factor — P/E and P/B cross-sectional ranking"
          />
          <CitationCard
            title="The Cross-Section of Volatility and Expected Returns"
            authors="Ang, Hodrick, Xing & Zhang"
            year={2006}
            application="Low-volatility factor — inverse of realized volatility and beta"
          />
          <CitationCard
            title="Insider Trading and the Information Content of Earnings Announcements"
            authors="Lakonishok & Lee"
            year={2001}
            application="Insider cluster score from SEC Form 4 filings"
          />
        </div>
      </section>

      {/* Universe */}
      <section className="max-w-6xl mx-auto px-6 py-20 border-t border-surface-container">
        <div className="grid md:grid-cols-3 gap-8">
          <Stat num="1000+" label="US + Indian tickers scored nightly" />
          <Stat num="5" label="ForeCast™ factors, sector-adjusted" />
          <Stat num="7" label="AI agents debate every thesis" />
        </div>
        <div className="mt-6 flex flex-col gap-2">
          <Link href="/sources" className="text-sm text-secondary hover:underline">
            View all 15+ data sources →
          </Link>
          <Link href="/compare" className="text-sm text-secondary hover:underline">
            See how NeuralQuant compares to ChatGPT, Claude & Grok →
          </Link>
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