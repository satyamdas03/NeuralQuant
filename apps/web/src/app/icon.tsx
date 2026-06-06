import { ImageResponse } from "next/og";

export const runtime = "edge";

const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          borderRadius: "20%",
          backgroundColor: "#0D1425",
          borderWidth: "1px",
          borderColor: "rgba(0, 255, 178, 0.3)",
          position: "relative",
        }}
      >
        <div
          style={{
            fontSize: 18,
            fontWeight: 800,
            color: "#00FFB2",
            letterSpacing: "-0.5px",
          }}
        >
          NQ
        </div>
      </div>
    ),
    { ...size }
  );
}