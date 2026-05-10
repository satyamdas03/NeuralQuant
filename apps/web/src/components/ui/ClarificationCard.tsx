"use client";

import { useState } from "react";
import type { ClarificationQuestion } from "@/lib/types";

interface Props {
  questions: ClarificationQuestion[];
  context?: string;
  onSubmit: (answers: string[]) => void;
}

export default function ClarificationCard({ questions, context, onSubmit }: Props) {
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    const result = questions.map((q, i) => answers[i] || "");
    onSubmit(result);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl bg-surface-container ghost-border p-4 space-y-4"
    >
      {context && (
        <div className="rounded-lg bg-primary/10 border border-primary/20 px-3 py-2">
          <p className="text-sm text-on-surface font-medium">{context}</p>
        </div>
      )}
      <p className="text-xs text-on-surface-variant">
        Help me personalize your answer:
      </p>

      {questions.map((q, qi) => (
        <div key={qi} className="space-y-2">
          <label className="block text-sm text-on-surface font-medium">
            {q.question}
          </label>
          {q.options.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {q.options.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() =>
                    setAnswers((prev) => ({ ...prev, [qi]: opt }))
                  }
                  className={`rounded-full px-3 py-1.5 text-xs font-medium border transition-colors ${
                    answers[qi] === opt
                      ? "bg-primary text-on-primary border-primary"
                      : "bg-surface-high text-on-surface-variant border-outline/20 hover:border-primary/40"
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          ) : (
            <input
              type="text"
              value={answers[qi] || ""}
              onChange={(e) =>
                setAnswers((prev) => ({ ...prev, [qi]: e.target.value }))
              }
              placeholder="Type your answer..."
              className="w-full rounded-lg bg-surface-high px-3 py-2 text-sm text-on-surface border border-outline/20 focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          )}
        </div>
      ))}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-on-primary hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {submitting ? "Getting Answer..." : "Answer & Continue"}
      </button>
    </form>
  );
}