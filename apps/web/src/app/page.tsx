// Public landing page. Authed users redirect to /dashboard.
import Link from "next/link";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function Landing() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (user) redirect("/dashboard");

  return (
    <div className="min-h-screen bg-black text-white">
      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,rgba(139,92,246,0.18),transparent_60%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,rgba(6,182,212,0.12),transparent_60%)]" />
        <div className="relative max-w-6xl mx-auto px-6 pt-20 pb-24 md:pt-32 md:pb-36">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/30 text-violet-300 text-xs font-medium mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />
            AI stock intelligence for US + India
          </div>
          <h1 className="text-4xl md:text-6xl font-bold tracking-tight leading-[1.05]">
            Institutional-grade equity research.
            <br />
            <span className="bg-gradient-to-r from-violet-400 via-fuchsia-400 to-cyan-400 bg-clip-text text-transparent">
              Powered by multi-agent AI.
            </span>
          </h1>
          <p className="mt-6 text-lg text-gray-400 max-w-2xl leading-relaxed">
            NeuralQuant fuses a 5-factor quant engine, regime detection, and a debate
            of specialist AI analysts into a single verdict per stock — across the
            S&amp;P 500 and NIFTY 500.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link
              href="/signup"
              className="px-6 py-3 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium text-sm transition-colors"
            >
              Get started free →
            </Link>
            <Link
              href="/login"
              className="px-6 py-3 rounded-lg border border-gray-700 hover:border-gray-500 text-gray-200 font-medium text-sm transition-colors"
            >
              Sign in
            </Link>
          </div>
          <div className="mt-10 flex flex-wrap gap-6 text-xs text-gray-500">
            <span>✓ No credit card</span>
            <span>✓ 50 queries / day free</span>
            <span>✓ US + Indian markets</span>
          </div>
        </div>
      </section>

      {/* What it does */}
      <section className="max-w-6xl mx-auto px-6 py-20 border-t border-gray-900">
        <h2 className="text-3xl md:text-4xl font-bold tracking-tight mb-3">
          Stop guessing. Start debating.
        </h2>
        <p className="text-gray-400 max-w-2xl">
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
            body="Ask in plain English: ‘₹10L across Indian midcaps’ or ‘low-vol US dividend names.’ Get a sized basket with return bands."
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
      <section className="max-w-6xl mx-auto px-6 py-20 border-t border-gray-900">
        <div className="grid md:grid-cols-3 gap-8">
          <Stat num="1000+" label="US + Indian tickers scored nightly" />
          <Stat num="5" label="Quant factors, sector-adjusted" />
          <Stat num="4" label="AI analysts debate every thesis" />
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-6xl mx-auto px-6 py-24 border-t border-gray-900">
        <div className="rounded-2xl bg-gradient-to-br from-violet-600/20 via-fuchsia-600/10 to-cyan-600/20 border border-violet-500/20 p-10 md:p-14 text-center">
          <h2 className="text-3xl md:text-4xl font-bold tracking-tight">
            Ready to see the full engine?
          </h2>
          <p className="mt-3 text-gray-400 max-w-xl mx-auto">
            Create a free account — screener, watchlist, portfolio builder, and
            AI debate unlock instantly.
          </p>
          <Link
            href="/signup"
            className="inline-block mt-8 px-8 py-3.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-semibold text-sm transition-colors"
          >
            Create free account →
          </Link>
        </div>
      </section>

      <footer className="max-w-6xl mx-auto px-6 py-10 text-xs text-gray-600 border-t border-gray-900">
        © {new Date().getFullYear()} NeuralQuant · Research tool, not investment advice.
      </footer>
    </div>
  );
}

function Feature({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/40 p-6 hover:border-gray-700 transition-colors">
      <h3 className="font-semibold text-gray-100">{title}</h3>
      <p className="mt-2 text-sm text-gray-400 leading-relaxed">{body}</p>
    </div>
  );
}

function Stat({ num, label }: { num: string; label: string }) {
  return (
    <div>
      <div className="text-4xl font-bold bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">
        {num}
      </div>
      <div className="mt-2 text-sm text-gray-400">{label}</div>
    </div>
  );
}
