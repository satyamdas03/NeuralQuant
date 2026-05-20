"use client";

import { useEffect, useRef, useState } from "react";
import { TrackReference, useTrackVolume } from "@livekit/components-react";

type AgentState = "initializing" | "idle" | "listening" | "thinking" | "speaking";

export default function QuantAstraFace({
  agentState,
  isSpeaking,
  audioTrack,
}: {
  agentState: AgentState;
  isSpeaking: boolean;
  audioTrack?: TrackReference;
}) {
  const [volume, setVolume] = useState(0);
  const animationRef = useRef<number>(0);

  // Use LiveKit's track volume hook for real audio levels during speaking
  const trackVolume = useTrackVolume(audioTrack);

  // Smooth volume transitions for lip sync effect
  useEffect(() => {
    const target = isSpeaking && trackVolume > 0.01 ? trackVolume : 0;
    const current = volume;
    const diff = target - current;
    const step = diff * 0.3; // Smooth easing

    if (Math.abs(diff) < 0.001) {
      setVolume(target);
      return;
    }

    animationRef.current = requestAnimationFrame(() => {
      setVolume(current + step);
    });

    return () => cancelAnimationFrame(animationRef.current);
  }, [trackVolume, isSpeaking, volume]);

  // Simulated mouth movement for "thinking" state
  useEffect(() => {
    if (agentState !== "thinking") return;
    const interval = setInterval(() => {
      setVolume((v) => (v > 0.1 ? 0.05 : 0.15));
    }, 400);
    return () => clearInterval(interval);
  }, [agentState]);

  const mouthScale = 0.3 + Math.min(volume * 12, 0.7);
  const eyeScale = 0.95 + Math.min(volume * 1.5, 0.05);
  const isActive = agentState === "speaking" || agentState === "thinking" || isSpeaking;
  const isLoading = agentState === "initializing";

  return (
    <div className="relative">
      {/* Glow ring */}
      <div
        className={`absolute inset-0 rounded-full blur-xl transition-all duration-500 ${
          isSpeaking
            ? "bg-primary-fixed/20 scale-125"
            : agentState === "thinking"
              ? "bg-amber-400/15 scale-115"
              : "bg-primary-fixed/5"
        } ${isLoading ? "animate-pulse" : ""}`}
      />

      {/* Face container */}
      <div
        className={`relative flex size-24 items-center justify-center rounded-full border-2 transition-all duration-500 ${
          isActive
            ? "border-primary-fixed/40 bg-surface-high/90 shadow-[0_0_30px_rgba(71,255,184,0.15)]"
            : "border-ghost-border bg-surface-high/60"
        }`}
      >
        <svg
          viewBox="0 0 100 100"
          className="size-16"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Eyes */}
          <ellipse
            cx="35"
            cy="38"
            rx={6 * eyeScale}
            ry={7 * eyeScale}
            fill="#e0e0e0"
            className="transition-all duration-200"
          />
          <ellipse
            cx="65"
            cy="38"
            rx={6 * eyeScale}
            ry={7 * eyeScale}
            fill="#e0e0e0"
            className="transition-all duration-200"
          />

          {/* Pupils */}
          <circle cx="35" cy="38" r="3" fill="#0d1425" />
          <circle cx="65" cy="38" r="3" fill="#0d1425" />

          {/* Mouth — scales with volume for lip sync effect */}
          <ellipse
            cx="50"
            cy={58 + mouthScale * 5}
            rx={10 + mouthScale * 3}
            ry={4 + mouthScale * 8}
            fill="#47ffb8"
            className="transition-all duration-150"
            opacity={0.9}
          />

          {/* Eyebrows */}
          <path
            d="M28 30 Q35 27 42 30"
            stroke="#47ffb8"
            strokeWidth="1.5"
            fill="none"
            className="transition-all duration-300"
          />
          <path
            d="M58 30 Q65 27 72 30"
            stroke="#47ffb8"
            strokeWidth="1.5"
            fill="none"
            className="transition-all duration-300"
          />
        </svg>
      </div>

      {/* Audio bars */}
      <div className="absolute -bottom-1 left-1/2 flex -translate-x-1/2 gap-0.5">
        {[0, 1, 2, 3, 4].map((i) => {
          const barHeight = isSpeaking
            ? 4 + Math.sin(Date.now() / 100 + i * 0.7) * volume * 24 + Math.random() * volume * 8
            : agentState === "thinking"
              ? 4 + Math.sin(Date.now() / 300 + i) * 8
              : 4;
          return (
            <div
              key={i}
              className="w-1 rounded-full bg-primary-fixed/60 transition-all duration-100"
              style={{ height: `${Math.max(barHeight, 3)}px` }}
            />
          );
        })}
      </div>
    </div>
  );
}
