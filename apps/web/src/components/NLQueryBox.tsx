"use client";
import { useState, useRef, useEffect } from "react";
import { api } from "@/lib/api";
import type { ConversationMessage } from "@/lib/types";

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
}

export function NLQueryBox({ defaultTicker }: { defaultTicker?: string }) {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const [slowLoad, setSlowLoad] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const slowTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const ask = async (question: string) => {
    const q = question.trim();
    if (!q || loading) return;
    setInput("");
    setSlowLoad(false);

    const userMsg: ChatMessage = { id: Date.now().toString(), role: "user", content: q };
    const placeholderId = (Date.now() + 1).toString();
    const placeholder: ChatMessage = { id: placeholderId, role: "assistant", content: "", loading: true };

    setMessages(prev => [...prev, userMsg, placeholder]);
    setLoading(true);

    // After 8s still loading → show cold-start warning
    slowTimer.current = setTimeout(() => setSlowLoad(true), 8000);

    // Build conversation history from prior completed turns
    const history: ConversationMessage[] = messages
      .filter(m => !m.loading)
      .map(m => ({ role: m.role, content: m.content }));

    try {
      const res = await api.runQuery({ question: q, ticker: defaultTicker, history });
      setMessages(prev =>
        prev.map(m =>
          m.id === placeholderId
            ? {
                ...m,
                content: res.answer,
                sources: res.data_sources,
                followUps: res.follow_up_questions,
                loading: false,
              }
            : m
        )
      );
    } catch {
      setMessages(prev =>
        prev.map(m =>
          m.id === placeholderId
            ? { ...m, content: "Query failed — backend may be warming up. Please try again in 30 seconds.", loading: false }
            : m
        )
      );
    } finally {
      setLoading(false);
      setSlowLoad(false);
      if (slowTimer.current) clearTimeout(slowTimer.current);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const clear = () => { setMessages([]); setInput(""); };

  return (
    <div className="flex flex-col h-full space-y-4">
      {/* Cold-start banner */}
      {slowLoad && (
        <div className="px-4 py-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center gap-2">
          <span className="text-amber-400 text-xs">⚡</span>
          <span className="text-amber-300 text-xs">
            Backend is warming up after inactivity — this may take 30–60 seconds. Please wait…
          </span>
        </div>
      )}

      {/* Chat history */}
      {messages.length > 0 ? (
        <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1 scroll-smooth">
          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              {msg.role === "user" ? (
                <div className="max-w-[80%] bg-violet-600/20 border border-violet-500/20 rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm text-gray-100">
                  {msg.content}
                </div>
              ) : (
                <div className="max-w-[90%] space-y-2">
                  <div className="flex items-start gap-2">
                    <div className="w-6 h-6 rounded-full bg-gradient-to-br from-violet-500 to-cyan-500 flex-shrink-0 flex items-center justify-center mt-0.5">
                      <span className="text-[10px] font-bold text-white">N</span>
                    </div>
                    <div className="bg-gray-900 border border-gray-800 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-gray-100 leading-relaxed">
                      {msg.loading ? (
                        <div className="flex gap-1.5 items-center py-1">
                          {[0,1,2].map(i => (
                            <span
                              key={i}
                              className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce"
                              style={{ animationDelay: `${i * 0.15}s` }}
                            />
                          ))}
                        </div>
                      ) : (
                        <p className="whitespace-pre-wrap">{msg.content}</p>
                      )}
                    </div>
                  </div>

                  {/* Sources */}
                  {!msg.loading && msg.sources && msg.sources.length > 0 && (
                    <div className="ml-8 flex gap-1.5 flex-wrap">
                      {msg.sources.map(s => (
                        <span key={s} className="text-[10px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
                          {s}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Follow-up suggestions */}
                  {!msg.loading && msg.followUps && msg.followUps.length > 0 && (
                    <div className="ml-8 flex flex-wrap gap-2">
                      {msg.followUps.map(q => (
                        <button
                          key={q}
                          onClick={() => ask(q)}
                          className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-full transition-colors border border-gray-700 hover:border-gray-600"
                        >
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      ) : (
        /* Empty state: example chips */
        <div className="space-y-3">
          <p className="text-xs text-gray-500 uppercase tracking-wider">Try asking</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLES.map(q => (
              <button
                key={q}
                onClick={() => ask(q)}
                className="text-xs px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded-full transition-colors border border-gray-700 hover:border-gray-600"
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input bar */}
      <div className="flex gap-2">
        <input
          ref={inputRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && !e.shiftKey && ask(input)}
          placeholder="Ask anything about markets, stocks, macro…"
          className="flex-1 px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white placeholder:text-gray-500 focus:outline-none focus:border-violet-500 text-sm transition-colors"
          disabled={loading}
        />
        <button
          onClick={() => ask(input)}
          disabled={loading || !input.trim()}
          className="px-5 py-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-xl text-white font-medium transition-colors text-sm"
        >
          {loading ? (
            <span className="w-4 h-4 rounded-full border-2 border-white/30 border-t-white animate-spin block" />
          ) : "→"}
        </button>
        {messages.length > 0 && (
          <button
            onClick={clear}
            className="px-3 py-3 text-gray-500 hover:text-gray-300 hover:bg-gray-800 rounded-xl transition-colors text-sm"
            title="Clear conversation"
          >
            ✕
          </button>
        )}
      </div>
    </div>
  );
}
