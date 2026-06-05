import { ImageResponse } from "next/og";
import { NextRequest } from "next/server";

export const runtime = "edge";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const backend = process.env.NEXT_PUBLIC_API_URL || "https://neuralquant.onrender.com";

  let ticker = "STOCK";
  let verdict = "HOLD";
  let score = 5;
  let irsPct: number | null = null;
  let found = false;

  try {
    const res = await fetch(`${backend}/share/analysis/${id}`, {
      next: { revalidate: 300 },
    });
    if (res.ok) {
      const data = (await res.json()) as Record<string, unknown>;
      ticker = String(data.ticker || "STOCK");
      verdict = String(data.verdict || "HOLD");
      score = Number(data.score ?? 5);
      const scoreData = (data.score_data ?? {}) as Record<string, unknown>;
      if (scoreData.irs_pct != null) {
        irsPct = Number(scoreData.irs_pct);
      }
      found = true;
    }
  } catch {
    // Fall through with defaults
  }

  const upperVerdict = verdict.toUpperCase();

  const isBull =
    upperVerdict.includes("BUY") || upperVerdict === "BULL";
  const isBear =
    upperVerdict.includes("SELL") || upperVerdict === "BEAR";

  const verdictLabel = isBull ? "BULL" : isBear ? "BEAR" : "NEUTRAL";
  const verdictColor = isBull
    ? "#22c55e"
    : isBear
      ? "#ef4444"
      : "#9ca3af";
  const verdictBg = isBull
    ? "rgba(34,197,94,0.15)"
    : isBear
      ? "rgba(239,68,68,0.15)"
      : "rgba(156,163,175,0.15)";

  const defaultOg = !found;

  const headers = new Headers();
  headers.set("Content-Type", "image/png");
  headers.set("Cache-Control", "public, s-maxage=3600, stale-while-revalidate=86400");

  return new ImageResponse(
    (
      <div
        style={{
          width: 1200,
          height: 630,
          background: "#0A0A0F",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          color: "#e5e7eb",
          fontFamily:
            'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Subtle radial glow */}
        <div
          style={{
            position: "absolute",
            top: -200,
            left: -200,
            width: 800,
            height: 800,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(71,255,184,0.06) 0%, transparent 70%)",
          }}
        />

        {/* Top-left accent line */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 4,
            background:
              "linear-gradient(90deg, #47ffb8, #8b5cf6, transparent)",
          }}
        />

        {defaultOg ? (
          /* Default OG when analysis not found */
          <>
            <div
              style={{
                fontSize: 64,
                fontWeight: 800,
                color: "#ffffff",
                letterSpacing: "-2px",
                marginBottom: 24,
              }}
            >
              NeuralQuant
            </div>
            <div
              style={{
                fontSize: 28,
                color: "#9ca3af",
                fontWeight: 500,
                marginBottom: 48,
              }}
            >
              AI-Powered Stock Analysis
            </div>
            <div
              style={{
                fontSize: 18,
                color: "#6b7280",
                fontWeight: 400,
              }}
            >
              7-Agent PARA-DEBATE &middot; Institutional-Grade Research
            </div>
          </>
        ) : (
          /* Analysis-specific OG */
          <>
            {/* Ticker */}
            <div
              style={{
                fontSize: 96,
                fontWeight: 900,
                color: "#ffffff",
                letterSpacing: "-3px",
                lineHeight: 1,
                marginBottom: 32,
              }}
            >
              {ticker}
            </div>

            {/* Verdict pill */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: verdictBg,
                border: `2px solid ${verdictColor}`,
                borderRadius: 9999,
                padding: "12px 40px",
                marginBottom: 32,
              }}
            >
              <div
                style={{
                  width: 14,
                  height: 14,
                  borderRadius: "50%",
                  background: verdictColor,
                  marginRight: 12,
                }}
              />
              <div
                style={{
                  fontSize: 32,
                  fontWeight: 800,
                  color: verdictColor,
                  letterSpacing: "2px",
                }}
              >
                {verdictLabel}
              </div>
            </div>

            {/* Score row */}
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 12,
              }}
            >
              <div
                style={{
                  fontSize: 72,
                  fontWeight: 900,
                  color: "#ffffff",
                  lineHeight: 1,
                  fontFamily:
                    'ui-monospace, SFMono-Regular, Menlo, Monaco, "Cascadia Code", monospace',
                }}
              >
                {score.toFixed(1)}
              </div>
              <div
                style={{
                  fontSize: 28,
                  color: "#6b7280",
                  fontWeight: 600,
                }}
              >
                /10
              </div>
            </div>

            {/* IRS% */}
            {irsPct != null && (
              <div
                style={{
                  marginTop: 24,
                  fontSize: 24,
                  fontWeight: 700,
                  color: "#47ffb8",
                  fontFamily:
                    'ui-monospace, SFMono-Regular, Menlo, Monaco, "Cascadia Code", monospace',
                }}
              >
                IRS {irsPct.toFixed(1)}%
              </div>
            )}
          </>
        )}

        {/* Bottom-right branding */}
        <div
          style={{
            position: "absolute",
            bottom: 32,
            right: 40,
            display: "flex",
            alignItems: "center",
            gap: 10,
          }}
        >
          <div
            style={{
              width: 10,
              height: 10,
              borderRadius: "50%",
              background: "#47ffb8",
            }}
          />
          <div
            style={{
              fontSize: 20,
              fontWeight: 800,
              color: "#47ffb8",
              letterSpacing: "1px",
            }}
          >
            QuantAlpha
          </div>
        </div>

        {/* Bottom-left small text */}
        <div
          style={{
            position: "absolute",
            bottom: 32,
            left: 40,
            fontSize: 14,
            color: "#4b5563",
            fontWeight: 500,
          }}
        >
          neuralquant.co
        </div>
      </div>
    ),
    {
      width: 1200,
      height: 630,
      headers,
    },
  );
}
