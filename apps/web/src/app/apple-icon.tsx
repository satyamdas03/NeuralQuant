import { ImageResponse } from "next/og";

export const runtime = "edge";

const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "22%",
          backgroundColor: "#0D1425",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Subtle border accent */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: "22%",
            borderWidth: "2px",
            borderColor: "rgba(0, 255, 178, 0.3)",
            borderStyle: "solid",
          }}
        />

        {/* Radial glow */}
        <div
          style={{
            position: "absolute",
            width: "70%",
            height: "70%",
            borderRadius: "50%",
            background:
              "radial-gradient(ellipse, rgba(0,255,178,0.08) 0%, transparent 70%)",
          }}
        />

        {/* NQ Monogram */}
        <div
          style={{
            fontSize: 90,
            fontWeight: 800,
            color: "#00FFB2",
            letterSpacing: "-2px",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          NQ
        </div>
      </div>
    ),
    { ...size }
  );
}