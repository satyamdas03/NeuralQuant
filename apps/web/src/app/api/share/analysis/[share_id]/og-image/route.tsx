import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";

export const runtime = "edge";
export const revalidate = 300; // 5 min cache

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ share_id: string }> }
) {
  const { share_id } = await params;
  const backend = process.env.NEXT_PUBLIC_API_URL || "https://neuralquant.onrender.com";

  let ticker = "STOCK";
  let verdict = "HOLD";
  let score = 5;

  try {
    const res = await fetch(`${backend}/share/analysis/${share_id}`, {
      next: { revalidate: 300 },
    });
    if (res.ok) {
      const data = await res.json();
      ticker = String(data.ticker || "STOCK");
      verdict = String(data.verdict || "HOLD");
      score = Number(data.score ?? 5);
    }
  } catch {
    // Fall through with defaults
  }

  const verdictColor =
    verdict.includes("BUY") || verdict === "BULL" ? "#4ade80" :
    verdict.includes("SELL") || verdict === "BEAR" ? "#ef4444" :
    "#eab308";

  const verdictLabel =
    verdict.includes("BUY") || verdict === "BULL" ? "BULL" :
    verdict.includes("SELL") || verdict === "BEAR" ? "BEAR" :
    "NEUTRAL";

  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          background: "#0f0f1a",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: "#e0e0e0",
          fontFamily: "system-ui, sans-serif",
          position: "relative",
        }}
      >
        {/* Grid overlay */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: "linear-gradient(135deg, rgba(0,255,178,0.03) 0%, transparent 50%, rgba(193,193,255,0.03) 100%)",
          }}
        />
        {/* Ticker */}
        <div style={{ fontSize: 80, fontWeight: 800, color: "#c1c1ff", letterSpacing: "-2px" }}>
          {ticker}
        </div>
        {/* Verdict */}
        <div style={{ fontSize: 36, marginTop: 16, color: verdictColor, fontWeight: 700 }}>
          {verdictLabel}
        </div>
        {/* Score */}
        <div style={{ fontSize: 48, marginTop: 12, fontWeight: 700, fontFamily: "monospace" }}>
          {score.toFixed(1)}
          <span style={{ fontSize: 24, color: "#a0a0b0" }}>/10</span>
        </div>
        {/* Branding */}
        <div style={{ fontSize: 18, marginTop: 48, color: "#7a7a8a", fontWeight: 500 }}>
          NeuralQuant AI Stock Analysis
        </div>
        {/* Subtitle */}
        <div style={{ fontSize: 14, marginTop: 8, color: "#5a5a6a" }}>
          7-Agent PARA-DEBATE • Institutional-Grade Research
        </div>
        {/* Accent line */}
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 4,
            background: "linear-gradient(90deg, #00ffb2, #c1c1ff)",
          }}
        />
      </div>
    ),
    { width: 1200, height: 630 }
  );
}