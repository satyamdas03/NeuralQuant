import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "NeuralQuant — AI Stock Intelligence";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          backgroundColor: "#0D1425",
          padding: "60px 80px",
          fontFamily: "system-ui, sans-serif",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Gradient accent lines */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            height: 6,
            background: "linear-gradient(90deg, #00FFB2, #00C9A7, #00FFB2)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: 0,
            left: 0,
            right: 0,
            height: 6,
            background: "linear-gradient(90deg, #00FFB2, #00C9A7, #00FFB2)",
          }}
        />

        {/* Radial glow */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            width: 800,
            height: 400,
            background: "radial-gradient(ellipse, rgba(0,255,178,0.08) 0%, transparent 70%)",
            pointerEvents: "none",
          }}
        />

        {/* Logo */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 20,
            marginBottom: 40,
          }}
        >
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: 18,
              background: "linear-gradient(135deg, #00FFB2 0%, #00C9A7 100%)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 36,
              fontWeight: 900,
              color: "#0D1425",
              boxShadow: "0 0 40px rgba(0,255,178,0.3)",
            }}
          >
            NQ
          </div>
          <span
            style={{
              fontSize: 42,
              fontWeight: 800,
              color: "#E8F4FF",
              letterSpacing: 2,
            }}
          >
            NeuralQuant
          </span>
        </div>

        {/* Tagline */}
        <div
          style={{
            fontSize: 28,
            color: "#8B9BB4",
            textAlign: "center",
            maxWidth: 900,
            lineHeight: 1.4,
            marginBottom: 40,
          }}
        >
          Institutional-Grade AI Stock Intelligence for US &amp; India Markets
        </div>

        {/* Feature pills */}
        <div
          style={{
            display: "flex",
            gap: 16,
            flexWrap: "wrap",
            justifyContent: "center",
          }}
        >
          {["IRS% Scoring", "PARA-DEBATE", "Regime Detection", "Screener", "Portfolio Intel"].map(
            (label) => (
              <div
                key={label}
                style={{
                  padding: "10px 24px",
                  borderRadius: 24,
                  backgroundColor: "rgba(0,255,178,0.1)",
                  border: "1px solid rgba(0,255,178,0.3)",
                  color: "#00FFB2",
                  fontSize: 16,
                  fontWeight: 600,
                  letterSpacing: 0.5,
                }}
              >
                {label}
              </div>
            )
          )}
        </div>

        {/* Footer */}
        <div
          style={{
            position: "absolute",
            bottom: 24,
            right: 40,
            fontSize: 13,
            color: "#4A5568",
          }}
        >
          neuralquant.co
        </div>
      </div>
    ),
    { ...size }
  );
}