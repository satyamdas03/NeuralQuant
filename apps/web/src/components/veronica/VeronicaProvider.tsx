"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useDataChannel,
  useIsSpeaking,
  useLocalParticipant,
  useRemoteParticipants,
} from "@livekit/components-react";
import { createClient } from "@/lib/supabase/client";
import { isQuietRoute, useVeronicaExternalState } from "@/lib/veronica-store";
import { useWakeWord } from "@/lib/useWakeWord";
import VeronicaOrb, { type OrbState } from "./VeronicaOrb";

const IDLE_LIMIT_MS = 5 * 60 * 1000;
const API = process.env.NEXT_PUBLIC_API_URL || "";

type PageInfo = { pageType: string; ticker: string | null };

function pageInfoFor(pathname: string): PageInfo {
  const stock = pathname.match(/^\/stocks\/([^/]+)/);
  if (stock) return { pageType: "stock_detail", ticker: decodeURIComponent(stock[1]) };
  const map: Record<string, string> = {
    "/dashboard": "dashboard",
    "/portfolio": "portfolio",
    "/hermes": "hermes_live_trading",
    "/analytics": "analytics",
    "/performance": "performance",
    "/compare": "compare",
    "/sources": "sources",
  };
  for (const [prefix, pageType] of Object.entries(map)) {
    if (pathname.startsWith(prefix)) return { pageType, ticker: null };
  }
  return { pageType: "page", ticker: null };
}

export default function VeronicaProvider() {
  const [orb, setOrb] = useState<OrbState>("idle");
  const [hint, setHint] = useState<string | null>(null);
  const [conn, setConn] = useState<{ token: string; url: string } | null>(null);
  const startedAtRef = useRef<number>(0);
  const retriedRef = useRef(false);
  const briefingRef = useRef(false);
  // Captured at connect time so session_end can attach it synchronously
  // (pagehide can't await). Without the Bearer, /analytics/track stores
  // user_id=null and the daily-cap query would treat every session as an
  // orphan start (600s each).
  const accessTokenRef = useRef<string | null>(null);

  const logSessionEnd = useCallback(() => {
    if (!startedAtRef.current) return;
    const duration_s = Math.round((Date.now() - startedAtRef.current) / 1000);
    startedAtRef.current = 0;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (accessTokenRef.current) {
      headers.Authorization = `Bearer ${accessTokenRef.current}`;
    }
    try {
      fetch(`${API}/analytics/track`, {
        method: "POST",
        headers,
        keepalive: true,
        body: JSON.stringify({
          event_type: "veronica_session",
          properties: { category: "voice", label: "session_end", duration_s },
        }),
      }).catch(() => {});
    } catch {
      // ignore
    }
  }, []);

  const connect = useCallback(async () => {
    setHint(null);
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const accessToken = data.session?.access_token;
    if (!accessToken) {
      setHint("Sign in to meet Veronica");
      return;
    }
    accessTokenRef.current = accessToken;
    setOrb("connecting");
    try {
      const res = await fetch(`${API}/livekit/token`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${accessToken}`,
        },
        body: JSON.stringify({ agent: "veronica" }),
      });
      if (res.status === 401) {
        setOrb("idle");
        setHint("Sign in to meet Veronica");
        return;
      }
      if (res.status === 429) {
        setOrb("capped");
        setHint("Veronica's voice time is used up for today — back tomorrow.");
        return;
      }
      if (!res.ok) throw new Error(`token ${res.status}`);
      const body = await res.json();
      if (body.status === "unavailable" || !body.token) throw new Error("unavailable");
      briefingRef.current = Boolean(body.morning_briefing);
      startedAtRef.current = Date.now();
      setConn({ token: body.token, url: body.url });
      setOrb("listening");
    } catch {
      if (!retriedRef.current) {
        retriedRef.current = true;
        setTimeout(connect, 2000);
        return;
      }
      setOrb("unavailable");
      setHint(null);
    }
  }, []);

  const disconnect = useCallback(
    (next: OrbState) => {
      logSessionEnd();
      setConn(null);
      setOrb(next);
    },
    [logSessionEnd]
  );

  useEffect(() => {
    const handler = () => logSessionEnd();
    window.addEventListener("pagehide", handler);
    return () => window.removeEventListener("pagehide", handler);
  }, [logSessionEnd]);

  const onOrbClick = useCallback(() => {
    if (orb === "idle" || orb === "sleeping" || orb === "unavailable") {
      retriedRef.current = false;
      connect();
    }
  }, [orb, connect]);

  // "Hey Veronica" wakes her while sleeping/idle — browser-side, zero LiveKit
  // cost. No-op in unsupported browsers; orb click still works.
  const wakeActive = orb === "sleeping" || orb === "idle";
  useWakeWord(wakeActive, () => {
    if (orb === "sleeping" || orb === "idle" || orb === "unavailable") {
      retriedRef.current = false;
      connect();
    }
  });

  return (
    <>
      {conn && (
        <LiveKitRoom
          token={conn.token}
          serverUrl={conn.url}
          audio={true}
          video={false}
          connect={true}
          onDisconnected={() => disconnect("sleeping")}
        >
          <RoomAudioRenderer />
          <VeronicaSession
            setOrb={setOrb}
            onIdleTimeout={() => disconnect("sleeping")}
            briefing={briefingRef.current}
          />
        </LiveKitRoom>
      )}
      <VeronicaOrb state={orb} hint={hint} onClick={onOrbClick} />
    </>
  );
}

function VeronicaSession({
  setOrb,
  onIdleTimeout,
  briefing,
}: {
  setOrb: (s: OrbState) => void;
  onIdleTimeout: () => void;
  briefing: boolean;
}) {
  const pathname = usePathname();
  const { astraOpen, pageData } = useVeronicaExternalState();
  const quiet = astraOpen || isQuietRoute(pathname);

  const { localParticipant } = useLocalParticipant();
  const remoteParticipants = useRemoteParticipants();
  const agentParticipant = remoteParticipants[0];
  // useIsSpeaking throws if passed undefined — fall back to local participant
  const agentSpeaking = useIsSpeaking(agentParticipant ?? localParticipant);

  const narratedRef = useRef<Set<string>>(new Set());
  const lastActivityRef = useRef<number | null>(null);
  const briefingSentRef = useRef(false);

  // First connect of the day → ask the agent for a spoken morning briefing once
  // the agent has actually joined the room.
  useEffect(() => {
    if (!briefing || briefingSentRef.current || !localParticipant || !agentParticipant) return;
    briefingSentRef.current = true;
    localParticipant
      .publishData(new TextEncoder().encode(JSON.stringify({ type: "briefing" })), {
        reliable: true,
        topic: "veronica",
      })
      .catch(() => {});
  }, [briefing, localParticipant, agentParticipant]);

  // Initialize idle-activity timestamp on mount (Date.now() is impure — must
  // not be called during render).
  useEffect(() => {
    lastActivityRef.current = Date.now();
  }, []);

  useDataChannel(
    "veronica",
    useCallback((msg: { payload: Uint8Array }) => {
      try {
        const data = JSON.parse(new TextDecoder().decode(msg.payload));
        if (
          (data.type === "user_transcript" && data.is_final && data.text?.trim()) ||
          (data.type === "agent_transcript" && !data.final && data.text?.trim())
        ) {
          lastActivityRef.current = Date.now();
        }
      } catch {
        // ignore malformed messages
      }
    }, [])
  );

  useEffect(() => {
    setOrb(quiet ? "quiet" : agentSpeaking ? "speaking" : "listening");
    if (agentSpeaking) lastActivityRef.current = Date.now();
  }, [quiet, agentSpeaking, setOrb]);

  useEffect(() => {
    localParticipant?.setMicrophoneEnabled(!quiet).catch(() => {});
  }, [quiet, localParticipant]);

  useEffect(() => {
    if (!localParticipant) return;
    const { pageType, ticker } = pageInfoFor(pathname);
    const key = `${pageType}:${ticker ?? ""}`;
    const narrate = !quiet && !narratedRef.current.has(key);
    if (narrate) narratedRef.current.add(key);
    const payload = JSON.stringify({
      type: "page_context",
      route: pathname,
      pageType,
      ticker,
      narrate,
      keyData: pageData ?? undefined,
    });
    localParticipant
      .publishData(new TextEncoder().encode(payload), {
        reliable: true,
        topic: "veronica",
      })
      .catch(() => {});
  }, [pathname, quiet, localParticipant, pageData]);

  useEffect(() => {
    const interval = setInterval(() => {
      const last = lastActivityRef.current;
      if (last !== null && Date.now() - last > IDLE_LIMIT_MS) {
        onIdleTimeout();
      }
    }, 30_000);
    return () => clearInterval(interval);
  }, [onIdleTimeout]);

  return null;
}
