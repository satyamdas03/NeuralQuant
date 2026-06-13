"use client";

import { useEffect, useRef } from "react";

export function matchesWakeWord(transcript: string): boolean {
  const t = transcript.toLowerCase();
  return t.includes("veronica");
}

/**
 * Browser wake-word listener (Web Speech API). Runs ONLY while `active` is true
 * (Veronica sleeping/idle) so it never competes with the live LiveKit mic.
 * On hearing "veronica" it calls `onWake()`. No-op where SpeechRecognition is
 * unsupported (Firefox/Safari) — caller keeps the orb-click fallback.
 */
export function useWakeWord(active: boolean, onWake: () => void): void {
  const onWakeRef = useRef(onWake);
  onWakeRef.current = onWake;

  useEffect(() => {
    if (!active) return;
    const SR =
      (typeof window !== "undefined" &&
        ((window as unknown as { SpeechRecognition?: unknown }).SpeechRecognition ||
          (window as unknown as { webkitSpeechRecognition?: unknown }).webkitSpeechRecognition)) ||
      null;
    if (!SR) return; // unsupported browser — graceful no-op

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rec: any = new (SR as any)();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = "en-US";
    let stopped = false;

    rec.onresult = (e: { results: ArrayLike<{ 0: { transcript: string } }> }) => {
      for (let i = 0; i < e.results.length; i++) {
        if (matchesWakeWord(e.results[i][0].transcript)) {
          stopped = true;
          try { rec.stop(); } catch { /* ignore */ }
          onWakeRef.current();
          return;
        }
      }
    };
    rec.onend = () => {
      if (!stopped) {
        try { rec.start(); } catch { /* ignore */ }
      }
    };
    rec.onerror = () => { /* swallow no-speech / not-allowed; onend will restart */ };

    try { rec.start(); } catch { /* ignore */ }
    return () => {
      stopped = true;
      try { rec.stop(); } catch { /* ignore */ }
    };
  }, [active]);
}
