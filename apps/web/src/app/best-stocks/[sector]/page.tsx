import type { Metadata } from "next";
import Link from "next/link";

const SECTORS: Record<string, { name: string; tickers: string[]; description: string }> = {
  banking: {
    name: "Banking",
    tickers: ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "KOTAKBANK.NS", "AXISBANK.NS", "INDUSINDBK.NS", "BANDHANBNK.NS", "AUBANK.NS", "FEDERALBNK.NS", "PNB.NS"],
    description: "Top banking stocks in India ranked by NeuralQuant 5-factor AI scoring. Quality, momentum, value, low-vol, and delivery analysis.",
  },
  it: {
    name: "IT & Technology",
    tickers: ["TCS.NS", "INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS", "LTIM.NS", "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "LTTS.NS"],
    description: "Best IT stocks in India by NeuralQuant AI scoring. 5-factor analysis including quality, momentum, and value.",
  },
  pharma: {
    name: "Pharmaceuticals",
    tickers: ["SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "APOLLOHOSP.NS", "TORNTPHARM.NS", "BIOCON.NS", "LUPIN.NS", "CADILAHC.NS", "ALKEM.NS"],
    description: "Top pharma stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  auto: {
    name: "Automobile",
    tickers: ["MARUTI.NS", "TATAMOTORS.NS", "M&M.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "EICHERMOT.NS", "ASHOKLEY.NS", "MOTHERSON.NS", "BOSCHLTD.NS", "TVSMOTOR.NS"],
    description: "Best auto stocks in India by NeuralQuant AI scoring.",
  },
  energy: {
    name: "Energy & Oil",
    tickers: ["RELIANCE.NS", "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "COALINDIA.NS", "BPCL.NS", "IOC.NS", "HINDPETRO.NS", "GAIL.NS", "ADANIGREEN.NS"],
    description: "Top energy stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  fmcg: {
    name: "FMCG",
    tickers: ["HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "TATACONSUM.NS", "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "COLPAL.NS", "EMAMILTD.NS"],
    description: "Best FMCG stocks in India by NeuralQuant AI scoring.",
  },
  metals: {
    name: "Metals & Mining",
    tickers: ["TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "ADANIENT.NS", "SAIL.NS", "VEDL.NS", "NMDC.NS", "HINDCOPPER.NS", "MOIL.NS", "NATIONALUM.NS"],
    description: "Top metal stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  telecom: {
    name: "Telecom",
    tickers: ["BHARTIARTL.NS", "IDEA.NS", "TATACOMM.NS", "INDHOTEL.NS"],
    description: "Best telecom stocks in India by NeuralQuant AI scoring.",
  },
  infrastructure: {
    name: "Infrastructure",
    tickers: ["LT.NS", "ULTRACEMCO.NS", "ADANIPORTS.NS", "SHREECEM.NS", "ACC.NS", "AMBUJA.NS", "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS"],
    description: "Top infrastructure stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  "financial-services": {
    name: "Financial Services",
    tickers: ["BAJFINANCE.NS", "BAJAJFINSV.NS", "SHRIRAMFIN.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS", "MANAPPURAM.NS", "BAJAJHLDNG.NS", "LICHSGFIN.NS", "PFC.NS", "RECLTD.NS"],
    description: "Best financial services stocks in India by NeuralQuant AI scoring.",
  },
  cement: {
    name: "Cement",
    tickers: ["ULTRACEMCO.NS", "SHREECEM.NS", "ACC.NS", "AMBUJA.NS", "DALMIACEM.NS", "RAMCOCEM.NS", "JKCEMENT.NS", "BOMDCEM.NS", "INDIACEM.NS", "HEIDELBERG.NS"],
    description: "Top cement stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  chemicals: {
    name: "Chemicals",
    tickers: ["PIDILITIND.NS", "ATUL.NS", "SRF.NS", "DEEPAKNTR.NS", "TATAELXSI.NS", "NAVINFLUOR.NS", "AARTIDRUGS.NS", "VINATIORGA.NS", "BALAMINES.NS", "CLEAN.NS"],
    description: "Best chemical stocks in India by NeuralQuant AI scoring.",
  },
  "consumer-durables": {
    name: "Consumer Durables",
    tickers: ["TITAN.NS", "VOLTAS.NS", "BLUESTARCO.NS", "HAVELLS.NS", "ORIENTELEC.NS", "BAJAJELEC.NS", "WHIRLPOOL.NS", "CROMPTON.NS", "AMBER.NS", "BUTTERFLY.NS"],
    description: "Top consumer durable stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
  "real-estate": {
    name: "Real Estate",
    tickers: ["DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "BRIGADE.NS", "SOBHA.NS", "PHOENIXLTD.NS", "NBCC.NS", "HIRANANDANI.NS"],
    description: "Best real estate stocks in India by NeuralQuant AI scoring.",
  },
  media: {
    name: "Media & Entertainment",
    tickers: ["ZEEL.NS", "SUNTV.NS", "PVR.NS", "INOXLEISUR.NS", "NETWORK18.NS", "DBL.NS"],
    description: "Top media stocks in India ranked by NeuralQuant 5-factor AI scoring.",
  },
};

export async function generateMetadata({
  params,
}: {
  params: Promise<{ sector: string }>;
}): Promise<Metadata> {
  const { sector } = await params;
  const data = SECTORS[sector];
  if (!data) return { title: "Sector Not Found" };

  return {
    title: `Best ${data.name} Stocks in India 2026 — NeuralQuant AI Analysis`,
    description: data.description,
    alternates: {
      canonical: `https://neuralquant.vercel.app/best-stocks/${sector}`,
    },
  };
}

export function generateStaticParams() {
  return Object.keys(SECTORS).map((sector) => ({ sector }));
}

export default async function SectorPage({
  params,
}: {
  params: Promise<{ sector: string }>;
}) {
  const { sector } = await params;
  const data = SECTORS[sector];

  if (!data) {
    return <div className="p-10 text-center text-on-surface-variant">Sector not found</div>;
  }

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      <div className="max-w-6xl mx-auto px-6 py-20">
        <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium mb-4">
          NeuralQuant ForeCast&trade;
        </span>
        <h1 className="font-headline text-4xl md:text-5xl font-bold tracking-tight">
          Best {data.name} Stocks in India
        </h1>
        <p className="mt-4 text-on-surface-variant max-w-2xl">
          {data.description} Updated nightly with live market data.
        </p>

        <div className="mt-12 grid gap-4 md:grid-cols-2">
          {data.tickers.map((ticker) => {
            const name = ticker.replace(".NS", "").replace(/-/g, " ");
            return (
              <Link
                key={ticker}
                href={`/stocks/${ticker}`}
                className="rounded-xl ghost-border bg-surface-low/40 p-6 hover-glow transition-colors flex justify-between items-center"
              >
                <div>
                  <div className="font-semibold text-on-surface">{name}</div>
                  <div className="text-sm text-on-surface-variant">{ticker}</div>
                </div>
                <span className="text-primary text-sm font-medium">View analysis &rarr;</span>
              </Link>
            );
          })}
        </div>

        <div className="mt-16 text-center">
          <p className="text-on-surface-variant text-sm">
            Want full 5-factor scores + AI debate for these stocks?
          </p>
          <Link
            href="/signup"
            className="mt-4 inline-block px-6 py-3 rounded-xl bg-gradient-to-r from-[#c1c1ff] to-[#bdf4ff] text-[#0f0f1a] font-semibold text-sm"
          >
            Create free account
          </Link>
        </div>
      </div>
    </div>
  );
}