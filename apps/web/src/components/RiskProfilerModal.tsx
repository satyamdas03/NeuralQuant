"use client";

import { useState } from "react";
import { authedApi } from "@/lib/api";
import type { AstraRiskProfile } from "@/lib/types";
import { Shield, TrendingUp, Zap, Loader2 } from "lucide-react";

interface RiskProfilerModalProps {
  onComplete: (profile: AstraRiskProfile) => void;
  onClose?: () => void;
}

type Step = 1 | 2 | 3;

const QUESTIONS = [
  {
    step: 1 as Step,
    question: "How would you react if your portfolio dropped 20% in a month?",
    icon: Shield,
    options: [
      { label: "Sell immediately to preserve capital", value: "conservative" as const },
      { label: "Hold and wait for recovery", value: "balanced" as const },
      { label: "Buy more — it's a discount", value: "aggressive" as const },
    ],
  },
  {
    step: 2 as Step,
    question: "What's your primary investment goal?",
    icon: TrendingUp,
    options: [
      { label: "Capital preservation — avoid losses", value: "conservative" as const },
      { label: "Steady growth — beat inflation", value: "balanced" as const },
      { label: "Maximum returns — willing to take big risks", value: "aggressive" as const },
    ],
  },
  {
    step: 3 as Step,
    question: "How would you describe your investment experience?",
    icon: Zap,
    options: [
      { label: "Beginner — still learning the basics", value: "conservative" as const },
      { label: "Intermediate — I understand markets", value: "balanced" as const },
      { label: "Advanced — I actively manage my portfolio", value: "aggressive" as const },
    ],
  },
];

function mapToRiskProfile(answers: string[]): AstraRiskProfile {
  const scores = { conservative: 0, balanced: 1, aggressive: 2 };
  const total = answers.reduce((sum, a) => sum + (scores[a as keyof typeof scores] ?? 1), 0);
  if (total <= 2) return "low";
  if (total <= 4) return "high";
  return "very_high";
}

const PROFILE_COLORS: Record<AstraRiskProfile, { bg: string; text: string; label: string }> = {
  low: { bg: "bg-primary-fixed/15", text: "text-primary-fixed", label: "Conservative" },
  high: { bg: "bg-amber-500/15", text: "text-amber-400", label: "Growth" },
  very_high: { bg: "bg-red-500/15", text: "text-red-400", label: "Aggressive" },
};

export default function RiskProfilerModal({ onComplete, onClose }: RiskProfilerModalProps) {
  const [step, setStep] = useState<Step>(1);
  const [answers, setAnswers] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentQ = QUESTIONS[step - 1];
  const Icon = currentQ.icon;

  const handleSelect = (value: string) => {
    const newAnswers = [...answers];
    newAnswers[step - 1] = value;
    setAnswers(newAnswers);

    if (step < 3) {
      setStep((step + 1) as Step);
    } else {
      // Final step — save and complete
      const profile = mapToRiskProfile(newAnswers);
      setSaving(true);
      authedApi.saveRiskProfile(profile)
        .then(() => onComplete(profile))
        .catch((e) => {
          setError(e instanceof Error ? e.message : "Failed to save profile");
          setSaving(false);
        });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="glass strong ghost-border rounded-xl max-w-md w-full mx-4 p-6 space-y-5">
        {/* Close button */}
        {onClose && (
          <button onClick={onClose} className="absolute top-4 right-4 text-on-surface-variant hover:text-on-surface">
            ✕
          </button>
        )}

        {/* Progress */}
        <div className="flex items-center gap-2">
          {[1, 2, 3].map((s) => (
            <div
              key={s}
              className={`h-1 flex-1 rounded-full transition-colors ${
                s <= step ? "bg-primary-fixed" : "bg-surface-container"
              }`}
            />
          ))}
        </div>

        {/* Question */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary-fixed/10 flex items-center justify-center">
            <Icon size={20} className="text-primary-fixed" />
          </div>
          <div>
            <span className="text-[10px] font-mono uppercase tracking-wider text-on-surface-variant">
              Question {step} of 3
            </span>
            <h3 className="text-sm font-medium text-on-surface leading-tight">
              {currentQ.question}
            </h3>
          </div>
        </div>

        {/* Options */}
        <div className="space-y-2">
          {currentQ.options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => handleSelect(opt.value)}
              disabled={saving}
              className="w-full text-left px-4 py-3 rounded-lg ghost-border hover:bg-surface-container-high hover:border-primary-fixed/40 transition-all duration-200 disabled:opacity-50"
            >
              <span className="text-sm text-on-surface">{opt.label}</span>
            </button>
          ))}
        </div>

        {/* Loading */}
        {saving && (
          <div className="flex items-center justify-center gap-2 py-2">
            <Loader2 size={16} className="animate-spin text-primary" />
            <span className="text-sm text-on-surface-variant">Saving your risk profile…</span>
          </div>
        )}

        {error && (
          <p className="text-sm text-error text-center">{error}</p>
        )}

        {/* Result preview (if step 3 completed) */}
        {step === 3 && answers.length === 3 && !saving && (
          <div className="text-center text-sm text-on-surface-variant">
            Your profile:{" "}
            <span className="font-bold">
              {PROFILE_COLORS[mapToRiskProfile(answers)].label}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export { mapToRiskProfile, PROFILE_COLORS };