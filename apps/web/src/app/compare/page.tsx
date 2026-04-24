"use client";

import { useState } from "react";
import Link from "next/link";
import {
  COMPARE_QUESTIONS,
  type CompareQuestion,
  type Winner,
} from "@/data/compare-questions";
import GlassPanel from "@/components/ui/GlassPanel";
import GhostBorderCard from "@/components/ui/GhostBorderCard";
import GradientButton from "@/components/ui/GradientButton";
import { ArrowLeft, Check, Minus, X, ArrowRight } from "lucide-react";

const AI_LABELS = {
  neuralquant: {
    name: "NeuralQuant",
    color: "text-tertiary",
    bg: "bg-tertiary/10",
  },
  chatgpt: { name: "ChatGPT", color: "text-primary", bg: "bg-primary/10" },
  claude: { name: "Claude", color: "text-secondary", bg: "bg-secondary/10" },
  grok: {
    name: "Grok",
    color: "text-on-surface-variant",
    bg: "bg-surface-high",
  },
} as const;

function WinnerIcon({ winner }: { winner: Winner }) {
  if (winner === "neuralquant")
    return <Check size={14} className="text-tertiary" />;
  if (winner === "partial")
    return <Minus size={14} className="text-primary" />;
  return <X size={14} className="text-error" />;
}

export default function ComparePage() {
  const [expanded, setExpanded] = useState<string | null>(null);

  const neuralquantWins = COMPARE_QUESTIONS.filter(
    (q) => q.winner === "neuralquant"
  ).length;

  return (
    <div className="min-h-screen bg-surface text-on-surface">
      {/* Header */}
      <div className="max-w-6xl mx-auto px-6 pt-20 pb-8">
        <Link
          href="/dashboard"
          className="inline-flex items-center gap-1 text-sm text-on-surface-variant hover:text-on-surface transition-colors mb-6"
        >
          <ArrowLeft size={16} /> Dashboard
        </Link>
        <h1 className="font-headline text-4xl md:text-5xl font-bold tracking-tight">
          Why NeuralQuant beats general AI
        </h1>
        <p className="mt-4 text-lg text-on-surface-variant max-w-2xl">
          We ran the same finance questions on NeuralQuant, ChatGPT, Claude, and
          Grok. Here&apos;s what happened.
        </p>
      </div>

      {/* Score summary */}
      <div className="max-w-6xl mx-auto px-6 pb-8">
        <GlassPanel strong>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <p className="text-sm text-on-surface-variant">
                Blind comparison across {COMPARE_QUESTIONS.length} finance tasks
              </p>
              <p className="mt-1 font-headline text-3xl font-bold">
                <span className="text-tertiary">{neuralquantWins}</span>
                <span className="text-on-surface-variant text-lg">
                  /{COMPARE_QUESTIONS.length}
                </span>
                <span className="text-on-surface-variant text-base ml-2">
                  NeuralQuant wins
                </span>
              </p>
            </div>
            <GradientButton href="/signup" size="md">
              Try it free <ArrowRight size={16} />
            </GradientButton>
          </div>
        </GlassPanel>
      </div>

      {/* Questions */}
      <div className="max-w-6xl mx-auto px-6 pb-20 space-y-6">
        {COMPARE_QUESTIONS.map((q) => (
          <CompareCard
            key={q.id}
            question={q}
            expanded={expanded === q.id}
            onToggle={() => setExpanded(expanded === q.id ? null : q.id)}
          />
        ))}
      </div>
    </div>
  );
}

function CompareCard({
  question,
  expanded,
  onToggle,
}: {
  question: CompareQuestion;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <GhostBorderCard className="cursor-pointer" hover>
      <button onClick={onToggle} className="w-full text-left">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <span className="text-xs text-on-surface-variant">
              {question.category}
            </span>
            <h3 className="font-semibold text-on-surface mt-1">
              {question.question}
            </h3>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <WinnerIcon winner={question.winner} />
            <span className="text-xs font-medium text-tertiary">NQ wins</span>
          </div>
        </div>
      </button>
      {expanded && (
        <div className="mt-4 space-y-3 border-t border-surface-container pt-4">
          {(
            Object.entries(question.responses) as [
              keyof typeof AI_LABELS,
              string,
            ][]
          ).map(([ai, response]) => {
            const label = AI_LABELS[ai];
            return (
              <div key={ai} className={`rounded-lg p-3 ${label.bg}`}>
                <p className={`text-xs font-semibold ${label.color} mb-1`}>
                  {label.name}
                </p>
                <p className="text-sm text-on-surface leading-relaxed">
                  {response}
                </p>
              </div>
            );
          })}
          <div className="rounded-lg bg-tertiary/5 border border-tertiary/20 p-3 mt-2">
            <p className="text-xs text-tertiary font-semibold">Verdict</p>
            <p className="text-sm text-on-surface mt-1">{question.verdict}</p>
          </div>
        </div>
      )}
    </GhostBorderCard>
  );
}