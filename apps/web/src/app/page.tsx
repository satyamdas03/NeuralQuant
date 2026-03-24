import { HeroButtons } from "@/components/hero-buttons";

export default function Home() {
  return (
    <div className="flex flex-col items-center text-center py-20 gap-8">
      <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-500/10 border border-violet-500/20 text-violet-400 text-sm">
        Institutional-grade AI. Retail price.
      </div>

      <h1 className="text-5xl md:text-7xl font-bold tracking-tight max-w-4xl">
        7 AI analysts debate{" "}
        <span className="bg-gradient-to-r from-violet-400 to-cyan-400 bg-clip-text text-transparent">
          every stock
        </span>{" "}
        so you don&apos;t have to
      </h1>

      <p className="text-xl text-gray-400 max-w-2xl">
        NeuralQuant runs a MACRO, FUNDAMENTAL, TECHNICAL, SENTIMENT, GEOPOLITICAL,
        and ADVERSARIAL analyst in parallel — then a HEAD ANALYST synthesises the debate
        into a single investment verdict. Transparent, explainable, real-time.
      </p>

      <HeroButtons />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8 text-sm">
        {[
          ["🇮🇳 India + US", "NSE/BSE + S&P 500"],
          ["🤖 7 AI Analysts", "PARA-DEBATE protocol"],
          ["🔍 Explainable", "See every signal driver"],
          ["⚡ Near-real-time", "Score updates on news"],
        ].map(([title, sub]) => (
          <div key={title} className="p-4 rounded-xl border border-gray-800 bg-gray-900/50">
            <div className="font-semibold">{title}</div>
            <div className="text-gray-500">{sub}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
