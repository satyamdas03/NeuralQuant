import { ImageResponse } from "next/og";
import { type NextRequest } from "next/server";

export const runtime = "edge";
export const alt = "NeuralQuant AI Stock Analysis";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.neuralquant.co";

const VERDICT_COLORS: Record<string, string> = {
  STRONG_BUY: "#47ffb8",
  BUY: "#47ffb8",
  BULL: "#47ffb8",
  HOLD: "#c1c1ff",
  NEUTRAL: "#c1c1ff",
  SELL: "#FF4158",
  STRONG_SELL: "#FF4158",
  BEAR: "#FF4158",
};

async function fetchShareData(shareId: string) {
  try {
    const res = await fetch(`${API_BASE}/share/analysis/${shareId}`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export default async function OGImage(request: NextRequest) {
  const shareId = request.nextUrl.pathname.split("/analysis/")[1]?.replace(/\/.*$/, "");
  const data = shareId ? await fetchShareData(shareId) : null;

  const ticker = (data?.ticker || "STOCK").toUpperCase();
  const market = data?.market || "US";
  const verdict = (data?.verdict || "HOLD").toUpperCase();
  const score = data?.score ?? 5;
  const accentColor = VERDICT_COLORS[verdict] || "#c1c1ff";

  const scoreBarWidth = `${Math.max(10, (score / 10) * 100)}%`;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#0a0e17",
          padding: "60px 80px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
            <div
              style={{
                width: 48,
                height: 48,
                borderRadius: 12,
                background: "linear-gradient(135deg, #47ffb8 0%, #00c9a7 100%)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 24,
                fontWeight: 900,
                color: "#0a0e17",
              }}
            >
              NQ
            </div>
            <span style={{ fontSize: 22, fontWeight: 600, color: "#E8F4FF", letterSpacing: 1 }}>
              NeuralQuant
            </span>
          </div>
          <span style={{ fontSize: 16, color: "#8b9bb4" }}>
            AI-Powered Stock Intelligence
          </span>
        </div>

        {/* Main content */}
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          {/* Ticker + Market */}
          <div style={{ display: "flex", alignItems: "baseline", gap: 16 }}>
            <span style={{ fontSize: 72, fontWeight: 900, color: "#E8F4FF", letterSpacing: -2 }}>
              {ticker}
            </span>
            <span
              style={{
                fontSize: 20,
                fontWeight: 600,
                color: "#8b9bb4",
                padding: "4px 12px",
                borderRadius: 8,
                backgroundColor: "rgba(255,255,255,0.06)",
              }}
            >
              {market === "IN" ? "NSE" : "NYSE/NASDAQ"}
            </span>
          </div>

          {/* Verdict + Score */}
          <div style={{ display: "flex", alignItems: "center", gap: 32 }}>
            <div
              style={{
                padding: "12px 28px",
                borderRadius: 12,
                backgroundColor: `${accentColor}18`,
                border: `2px solid ${accentColor}`,
                display: "flex",
                alignItems: "center",
                gap: 10,
              }}
            >
              <span style={{ fontSize: 28, fontWeight: 800, color: accentColor }}>
                {verdict.replace("_", " ")}
              </span>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ fontSize: 14, color: "#8b9bb4" }}>IRS% Composite Score</span>
                <span style={{ fontSize: 14, fontWeight: 700, color: "#E8F4FF" }}>{score}/10</span>
              </div>
              <div
                style={{
                  height: 10,
                  borderRadius: 5,
                  backgroundColor: "rgba(255,255,255,0.08)",
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    height: "100%",
                    width: scoreBarWidth,
                    borderRadius: 5,
                    background: `linear-gradient(90deg, ${accentColor}, ${accentColor}88)`,
                  }}
                />
              </div>
            </div>
          </div>

          {/* PARA-DEBATE label */}
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 16, color: "#8b9bb4" }}>Analyzed by</span>
            <span
              style={{
                fontSize: 16,
                fontWeight: 700,
                color: "#47ffb8",
                letterSpacing: 1,
              }}
            >
              PARA-DEBATE
            </span>
            <span style={{ fontSize: 16, color: "#8b9bb4" }}>— 7-Agent AI Consensus</span>
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderTop: "1px solid rgba(255,255,255,0.06)",
            paddingTop: 20,
          }}
        >
          <span style={{ fontSize: 13, color: "#5a6a80" }}>
            NeuralQuant is a research tool, not SEBI-registered investment advice.
          </span>
          <span style={{ fontSize: 13, color: "#5a6a80" }}>
            neuralquant.co
          </span>
        </div>
      </div>
    ),
    { ...size }
  );
}