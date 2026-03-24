"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import type { QueryResponse } from "@/lib/types";

const EXAMPLE_QUESTIONS = [
  "Why might RELIANCE outperform in a risk-off regime?",
  "What does a Piotroski score of 8 mean for a company?",
  "Which factors drive NeuralQuant's quality composite?",
  "How does the HMM regime detector work?",
  "What signals indicate a bear market regime?",
];

export function NLQueryBox({ defaultTicker }: { defaultTicker?: string }) {
  const [question, setQuestion] = useState("");
  const [response, setResponse] = useState<QueryResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const ask = async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setResponse(null);
    try {
      const r = await api.runQuery({ question: q, ticker: defaultTicker });
      setResponse(r);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-3">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && ask(question)}
          placeholder="Ask anything about stocks, factors, or the market..."
          className="flex-1 px-4 py-3 bg-gray-900 border border-gray-700 rounded-xl text-white placeholder:text-gray-500 focus:outline-none focus:border-violet-500"
        />
        <button
          onClick={() => ask(question)}
          disabled={loading || !question.trim()}
          className="px-6 py-3 bg-violet-600 hover:bg-violet-700 disabled:opacity-50 rounded-xl text-white font-medium transition-colors"
        >
          {loading ? "..." : "Ask"}
        </button>
      </div>

      {!response && !loading && (
        <div className="flex flex-wrap gap-2">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              onClick={() => { setQuestion(q); ask(q); }}
              className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white rounded-full transition-colors"
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {loading && (
        <div className="p-5 rounded-xl border border-gray-800 animate-pulse">
          <div className="h-4 bg-gray-800 rounded w-3/4 mb-2" />
          <div className="h-4 bg-gray-800 rounded w-1/2" />
        </div>
      )}

      {response && (
        <div className="space-y-4">
          <div className="p-5 rounded-2xl border border-gray-800 bg-gray-900/60">
            <p className="text-gray-100 leading-relaxed whitespace-pre-wrap">{response.answer}</p>
          </div>

          {response.data_sources.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              <span className="text-xs text-gray-500">Sources:</span>
              {response.data_sources.map((s) => (
                <span key={s} className="text-xs px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20">
                  {s}
                </span>
              ))}
            </div>
          )}

          {response.follow_up_questions.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs text-gray-500 uppercase tracking-wider">Follow-up questions</p>
              <div className="flex flex-wrap gap-2">
                {response.follow_up_questions.map((q) => (
                  <button
                    key={q}
                    onClick={() => { setQuestion(q); ask(q); }}
                    className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-full transition-colors"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
