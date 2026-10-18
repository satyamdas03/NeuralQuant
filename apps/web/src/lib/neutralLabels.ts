/**
 * B5: public surfaces must not show buy/sell/hold/avoid advice language.
 *
 * Stored verdicts (PARA-DEBATE head analyst, analyst consensus, IRS zones)
 * keep their raw values in the API. At the UI boundary they are mapped to
 * neutral research bands. Unknown values render as "Unrated", never as the
 * raw string.
 */

export type NeutralBand = "Upper band" | "Middle band" | "Lower band" | "Unrated";
export type BandTone = "positive" | "neutral" | "negative" | "none";

const UPPER = new Set(["STRONG BUY", "BUY", "OUTPERFORM", "ACCUMULATE", "OVERWEIGHT", "BULL", "BULLISH"]);
const MIDDLE = new Set(["HOLD", "NEUTRAL", "MARKET PERFORM", "EQUAL WEIGHT", "WATCH"]);
const LOWER = new Set([
  "SELL", "STRONG SELL", "HARD SELL", "AVOID", "UNDERPERFORM", "REDUCE", "UNDERWEIGHT", "BEAR", "BEARISH",
]);

function normalise(raw: string | null | undefined): string {
  return String(raw ?? "").trim().toUpperCase().replace(/[_-]+/g, " ").replace(/\s+/g, " ");
}

export function neutralBand(raw: string | null | undefined): NeutralBand {
  const v = normalise(raw);
  if (UPPER.has(v)) return "Upper band";
  if (MIDDLE.has(v)) return "Middle band";
  if (LOWER.has(v)) return "Lower band";
  return "Unrated";
}

export function bandTone(band: NeutralBand): BandTone {
  if (band === "Upper band") return "positive";
  if (band === "Middle band") return "neutral";
  if (band === "Lower band") return "negative";
  return "none";
}

/** IRS% research zones (thresholds unchanged: 65 / 45). */
export function irsBand(pct: number | null | undefined): NeutralBand {
  if (pct == null) return "Unrated";
  if (pct >= 65) return "Upper band";
  if (pct >= 45) return "Middle band";
  return "Lower band";
}

/** Replaces the old "HARD SELL" flag (G Score < -4). */
export const LOW_G_SCORE_FLAG = "G-SCORE < −4";
