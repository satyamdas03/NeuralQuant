"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";

// ── Types ─────────────────────────────────────────────────────────────────

type ActivityEntry = {
  activity_type: string;
  category: string;
  label?: string;
  payload?: Record<string, unknown>;
};

type SessionContextValue = {
  sessionId: string | null;
  sessionStarted: boolean;
  logActivity: (
    activityType: string,
    category: string,
    label?: string,
    payload?: Record<string, unknown>,
  ) => void;
  endSession: () => void;
};

const SessionContext = createContext<SessionContextValue>({
  sessionId: null,
  sessionStarted: false,
  logActivity: () => {},
  endSession: () => {},
});

const API_BASE = "/api";
const FLUSH_INTERVAL_MS = 5000;
const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 min
const MAX_QUEUE_SIZE = 50;

// ── Helpers ───────────────────────────────────────────────────────────────

function getStorageSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("nq_tracked_session_id");
}

function setStorageSessionId(id: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem("nq_tracked_session_id", id);
}

function clearStorageSessionId() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("nq_tracked_session_id");
}

async function createSession(): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/session/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        user_agent: navigator.userAgent,
        metadata: { url: window.location.href },
      }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.session_id;
  } catch {
    return null;
  }
}

async function flushActivities(
  sessionId: string,
  activities: ActivityEntry[],
): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/session/activity`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, activities }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function endSessionOnServer(sessionId: string): Promise<void> {
  try {
    await fetch(`${API_BASE}/session/end`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
  } catch {
    // Fire and forget — best effort
  }
}

// ── Provider ──────────────────────────────────────────────────────────────

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(getStorageSessionId);
  const sessionRef = useRef<string | null>(sessionId);
  const queueRef = useRef<ActivityEntry[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const idleRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hasStartedRef = useRef(!!sessionId);

  // Keep ref in sync
  useEffect(() => {
    sessionRef.current = sessionId;
  }, [sessionId]);

  // ── Flush timer ───────────────────────────────────────────────────────
  useEffect(() => {
    timerRef.current = setInterval(() => {
      const sid = sessionRef.current;
      const batch = queueRef.current.splice(0);
      if (batch.length > 0 && sid) {
        flushActivities(sid, batch);
      }
    }, FLUSH_INTERVAL_MS);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, []);

  // ── Idle timeout ──────────────────────────────────────────────────────
  const resetIdleTimer = useCallback(() => {
    if (idleRef.current) clearTimeout(idleRef.current);
    idleRef.current = setTimeout(() => {
      const sid = sessionRef.current;
      if (sid) {
        const batch = queueRef.current.splice(0);
        if (batch.length > 0) flushActivities(sid, batch);
        endSessionOnServer(sid);
        clearStorageSessionId();
        setSessionId(null);
      }
    }, IDLE_TIMEOUT_MS);
  }, []);

  // Start idle timer on mount
  useEffect(() => {
    resetIdleTimer();
    const onActivity = () => resetIdleTimer();
    window.addEventListener("mousemove", onActivity, { passive: true });
    window.addEventListener("keydown", onActivity, { passive: true });
    window.addEventListener("scroll", onActivity, { passive: true });
    window.addEventListener("click", onActivity, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onActivity);
      window.removeEventListener("keydown", onActivity);
      window.removeEventListener("scroll", onActivity);
      window.removeEventListener("click", onActivity);
      if (idleRef.current) clearTimeout(idleRef.current);
    };
  }, [resetIdleTimer]);

  // ── beforeunload — flush + end session ────────────────────────────────
  useEffect(() => {
    const onUnload = () => {
      const sid = sessionRef.current;
      if (!sid) return;
      const batch = queueRef.current.splice(0);
      if (batch.length > 0) {
        // Use sendBeacon for reliable delivery during unload
        const payload = JSON.stringify({ session_id: sid, activities: batch });
        navigator.sendBeacon?.(
          `${API_BASE}/session/activity`,
          new Blob([payload], { type: "application/json" }),
        );
      }
      // End session via sendBeacon
      navigator.sendBeacon?.(
        `${API_BASE}/session/end`,
        new Blob(
          [JSON.stringify({ session_id: sid })],
          { type: "application/json" },
        ),
      );
    };
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, []);

  // ── logActivity ───────────────────────────────────────────────────────
  const logActivity = useCallback(
    async (
      activityType: string,
      category: string,
      label?: string,
      payload?: Record<string, unknown>,
    ) => {
      resetIdleTimer();

      let sid = sessionRef.current;
      if (!sid) {
        sid = await createSession();
        if (!sid) return;
        sessionRef.current = sid;
        setSessionId(sid);
        setStorageSessionId(sid);
        hasStartedRef.current = true;
      }

      const entry: ActivityEntry = {
        activity_type: activityType,
        category,
        label,
        payload,
      };
      queueRef.current.push(entry);

      // Flush immediately if queue is large
      if (queueRef.current.length >= MAX_QUEUE_SIZE) {
        const batch = queueRef.current.splice(0);
        flushActivities(sid, batch);
      }
    },
    [resetIdleTimer],
  );

  // ── endSession ────────────────────────────────────────────────────────
  const endSession = useCallback(() => {
    const sid = sessionRef.current;
    if (!sid) return;

    // Flush remaining
    const batch = queueRef.current.splice(0);
    if (batch.length > 0) flushActivities(sid, batch);

    endSessionOnServer(sid);
    clearStorageSessionId();
    sessionRef.current = null;
    setSessionId(null);
    if (idleRef.current) clearTimeout(idleRef.current);
  }, []);

  return (
    <SessionContext.Provider
      value={{
        sessionId,
        sessionStarted: hasStartedRef.current,
        logActivity,
        endSession,
      }}
    >
      {children}
    </SessionContext.Provider>
  );
}

// ── Hook ─────────────────────────────────────────────────────────────────

export function useSessionTracker() {
  return useContext(SessionContext);
}
