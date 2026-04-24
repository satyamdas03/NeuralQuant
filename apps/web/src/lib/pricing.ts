export type Currency = "INR" | "USD";

export interface TierInfo {
  key: string;
  name: string;
  inrPrice: number;
  usdPrice: number;
  watchlists: number;
  queriesPerDay: number;
  backtestsPerDay: number;
  popular?: boolean;
}

export const TIERS: TierInfo[] = [
  {
    key: "free",
    name: "Free",
    inrPrice: 0,
    usdPrice: 0,
    watchlists: 5,
    queriesPerDay: 10,
    backtestsPerDay: 5,
  },
  {
    key: "investor",
    name: "Investor",
    inrPrice: 299,
    usdPrice: 9,
    watchlists: 25,
    queriesPerDay: 100,
    backtestsPerDay: 5,
    popular: true,
  },
  {
    key: "pro",
    name: "Pro",
    inrPrice: 999,
    usdPrice: 29,
    watchlists: 100,
    queriesPerDay: 1000,
    backtestsPerDay: 50,
  },
  {
    key: "api",
    name: "API",
    inrPrice: 4999,
    usdPrice: 149,
    watchlists: 1000,
    queriesPerDay: 100000,
    backtestsPerDay: 1000,
  },
];

export function formatPrice(amount: number, currency: Currency): string {
  if (amount === 0) return "Free forever";
  if (currency === "INR") return `₹${amount.toLocaleString("en-IN")}/mo`;
  return `$${amount}/mo`;
}

export function detectCurrency(): Currency {
  if (typeof navigator === "undefined") return "USD";
  const lang = navigator.language || "";
  if (lang.includes("IN") || lang.startsWith("hi")) return "INR";
  return "USD";
}