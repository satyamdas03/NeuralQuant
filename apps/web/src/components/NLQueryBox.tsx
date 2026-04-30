"use client";

import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import type { ConversationMessage, StructuredQueryResponse } from "@/lib/types";
import AIResponseCard from "@/components/ui/AIResponseCard";
import AIThinkingTimeline, { type PhaseEntry } from "@/components/ui/AIThinkingTimeline";
import SuggestionChips from "@/components/ui/SuggestionChips";
import ChatInputArea from "@/components/ui/ChatInputArea";
import GlassPanel from "@/components/ui/GlassPanel";

const EXAMPLES = [
  "What is the effect of Iran-US tensions on oil stocks?",
  "Which sectors benefit from rising yields?",
  "Why is the VIX elevated right now?",
  "Compare quality vs momentum in a Bear regime",
  "What does CPI at 2.4% mean for Fed policy?",
];

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  followUps?: string[];
  loading?: boolean;
  structured?: StructuredQueryResponse | null;
  phases?: PhaseEntry[];
}

export function NLQueryBox({ defaultTicker }: { defaultTicker?: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [slowLoad, setSlowLoad] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Force re-render every 500ms while a request is in flight so the timeline's
  // elapsed-time counters update visually. Without this, "0.0s" stays frozen
  // until the next phase event arrives.
  const [, forceTick] = useState(0);
  useEffect(() => {
    if (!loading) return;
    const id = setInterval(() => forceTick((t) => t + 1), 500);
    return () => clearInterval(id);
  }, [loading]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || loading) return;
    setSlowLoad(false);

    const userMsg: ChatMessage = { id: Date.now().toString(), role: "user", content: q };
    const phId = (Date.now() + 1).toString();
    const ph: ChatMessage = {
      id: phId,
      role: "assistant",
      content: "",
      loading: true,
      phases: [],
    };

    setMessages((prev) => [...prev, userMsg, ph]);
    setLoading(true);
    slowTimer.current = setTimeout(() => setSlowLoad(true), 12000);

    const history: ConversationMessage[] = messages
      .filter((m) => !m.loading)
      .map((m) => ({ role: m.role, content: m.content }));

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 300_000);

    try {
      const res = await api.runQueryStream(
        { question: q, ticker: defaultTicker, history },
        controller.signal,
        (phase, label) => {
          // Append new phase to the message's phase history; mark previous
          // phase as completed so the timeline shows ✓ on all prior steps.
          const now = Date.now();
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== phId) return m;
              const prevPhases = m.phases ?? [];
              const updated: PhaseEntry[] = prevPhases.map((p, idx) =>
                idx === prevPhases.length - 1 && p.completedAt === undefined
                  ? { ...p, completedAt: now }
                  : p
              );
              updated.push({ phase, label, startedAt: now });
              return { ...m, phases: updated };
            })
          );
        },
      );
      // Mark final phase as completed on result
      const completionTs = Date.now();
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== phId) return m;
          const closed: PhaseEntry[] = (m.phases ?? []).map((p) =>
            p.completedAt === undefined ? { ...p, completedAt: completionTs } : p
          );
          return {
            ...m,
            content: res.summary || "",
            sources: res.data_sources,
            followUps: res.follow_up_questions,
            loading: false,
            structured: res,
            phases: closed,
          };
        })
      );
    } catch (err) {
      const msg = err instanceof DOMException && err.name === "AbortError"
        ? "Query timed out after 5 minutes. Try a shorter question or retry."
        : "Query failed — backend may be warming up. Retry in 30s.";
      setMessages((prev) =>
        prev.map((m) =>
          m.id === phId ? { ...m, content: msg, loading: false } : m
        )
      );
    } finally {
      clearTimeout(timeout);
      setLoading(false);
      setSlowLoad(false);
      if (slowTimer.current) clearTimeout(slowTimer.current);
    }
  };

  const clear = () => setMessages([]);

  return (
    <GlassPanel strong className="flex flex-col space-y-4">
      {slowLoad && (
        <div className="rounded-lg bg-primary/10 px-3 py-2 text-xs text-primary border border-primary/20">
          Backend warming up — may take 30–60s. Please wait…
        </div>
      )}

      {messages.length > 0 ? (
        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1 scroll-smooth">
          {messages.map((msg) =>
            msg.role === "user" ? (
              <div key={msg.id} className="flex justify-end">
                <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-primary/15 border border-primary/20 px-4 py-2.5 text-sm text-on-surface">
                  {msg.content}
                </div>
              </div>
            ) : msg.loading ? (
              <div key={msg.id}>
                {msg.phases && msg.phases.length > 0 ? (
                  <AIThinkingTimeline phases={msg.phases} />
                ) : (
                  <div className="flex items-center gap-2 py-1 text-sm text-on-surface-variant">
                    <span className="animate-pulse text-primary">●</span>
                    <span>Connecting to NeuralQuant AI...</span>
                  </div>
                )}
              </div>
            ) : (
              <AIResponseCard
                key={msg.id}
                answer={msg.content}
                sources={msg.sources}
                structured={msg.structured}
              />
            )
          )}
          {messages.length > 0 && !loading && messages[messages.length - 1].followUps && (
            <SuggestionChips
              suggestions={messages[messages.length - 1].followUps!}
              onSelect={ask}
            />
          )}
          <div ref={bottomRef} />
        </div>
      ) : (
        <div className="space-y-3">
          <p className="text-xs uppercase tracking-wider text-on-surface-variant">Try asking</p>
          <SuggestionChips suggestions={EXAMPLES} onSelect={ask} />
        </div>
      )}

      <div className="flex items-end gap-2">
        <ChatInputArea onSubmit={ask} disabled={loading} />
        {messages.length > 0 && (
          <button
            onClick={clear}
            className="mb-0.5 rounded-xl px-3 py-2.5 text-on-surface-variant hover:bg-surface-high hover:text-on-surface transition-colors"
            title="Clear conversation"
          >
            ✕
          </button>
        )}
      </div>
    </GlassPanel>
  );
}