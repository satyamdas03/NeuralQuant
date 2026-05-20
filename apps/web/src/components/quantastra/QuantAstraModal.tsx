"use client";

import { useState, useEffect, useCallback } from "react";
import { Mic, X, Loader2 } from "lucide-react";
import QuantAstraCallView from "./QuantAstraCallView";

type ModalState = "intro" | "connecting" | "in-call" | "ended";

interface QuantAstraModalProps {
  onClose: () => void;
}

export default function QuantAstraModal({ onClose }: QuantAstraModalProps) {
  const [state, setState] = useState<ModalState>("intro");
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);

  const livekitUrl =
    process.env.NEXT_PUBLIC_LIVEKIT_URL || "wss://friday-1-few4r3qf.livekit.cloud";

  const fetchToken = useCallback(async () => {
    setState("connecting");
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "";
      const res = await fetch(`${apiUrl}/livekit/token`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }
      const data = await res.json();
      if (data.status === "unavailable") {
        throw new Error(data.message || "LiveKit is not configured");
      }
      setToken(data.token);
      setState("in-call");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to connect. Please try again."
      );
      setState("intro");
    }
  }, []);

  const handleCallEnded = useCallback(() => {
    setState("ended");
  }, []);

  // Close on Escape key
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[65] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="glass-strong ghost-border mx-4 w-full max-w-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-ghost-border px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-full bg-primary-fixed text-background">
              <Mic className="size-5" />
            </div>
            <div>
              <h2 className="font-headline text-lg font-semibold text-on-surface">
                QuantAstra
              </h2>
              <p className="text-xs text-on-surface-variant">
                AI Portfolio Manager · NeuralQuant
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-high hover:text-on-surface"
            aria-label="Close"
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-6">
          {state === "intro" && (
            <div className="flex flex-col items-center gap-6 py-8">
              <div className="flex size-20 items-center justify-center rounded-full bg-primary-fixed/10 ring-1 ring-primary-fixed/30">
                <Mic className="size-10 text-primary-fixed" />
              </div>
              <div className="text-center">
                <h3 className="text-xl font-semibold text-on-surface">
                  Talk to your Portfolio Manager
                </h3>
                <p className="mt-2 max-w-md text-sm text-on-surface-variant">
                  QuantAstra has 20 years of hedge fund experience and access to
                  NeuralQuant&apos;s full research platform. Ask anything about
                  your portfolio, specific stocks, market conditions, or
                  investment ideas.
                </p>
              </div>

              {error && (
                <p className="rounded-lg bg-error-container/20 px-4 py-2 text-sm text-error">
                  {error}
                </p>
              )}

              <button
                onClick={fetchToken}
                className="flex items-center gap-2 rounded-full bg-primary-fixed px-6 py-3 font-semibold text-background shadow-[0_0_20px_rgba(0,255,178,0.25)] transition-all hover:scale-105 hover:shadow-[0_0_35px_rgba(0,255,178,0.4)]"
              >
                <Mic className="size-4" />
                Start Call
              </button>

              <p className="text-xs text-on-surface-variant">
                Your microphone and camera will be requested for the call.
              </p>
            </div>
          )}

          {state === "connecting" && (
            <div className="flex flex-col items-center gap-4 py-16">
              <Loader2 className="size-10 animate-spin text-primary-fixed" />
              <p className="text-sm text-on-surface-variant">
                Connecting to QuantAstra...
              </p>
            </div>
          )}

          {state === "in-call" && (
            <QuantAstraCallView
              token={token}
              serverUrl={livekitUrl}
              onDisconnected={handleCallEnded}
            />
          )}

          {state === "ended" && (
            <div className="flex flex-col items-center gap-6 py-12">
              <div className="flex size-20 items-center justify-center rounded-full bg-surface-high">
                <Mic className="size-10 text-on-surface-variant" />
              </div>
              <div className="text-center">
                <h3 className="text-lg font-semibold text-on-surface">
                  Call Ended
                </h3>
                <p className="mt-2 text-sm text-on-surface-variant">
                  Thanks for talking with QuantAstra. You can start a new call
                  anytime.
                </p>
              </div>
              <div className="flex gap-3">
                <button
                  onClick={fetchToken}
                  className="rounded-full bg-primary-fixed px-5 py-2.5 text-sm font-semibold text-background transition-all hover:scale-105"
                >
                  Call Again
                </button>
                <button
                  onClick={onClose}
                  className="rounded-full bg-surface-high px-5 py-2.5 text-sm font-medium text-on-surface transition-colors hover:bg-surface-highest"
                >
                  Close
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
