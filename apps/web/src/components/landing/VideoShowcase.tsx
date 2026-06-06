"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Play, X, BarChart3, Brain, Shield } from "lucide-react";
import GhostBorderCard from "@/components/ui/GhostBorderCard";

const PLACEHOLDER_VIDEO_URL = "https://www.youtube.com/embed/dQw4w9WgXcQ"; // placeholder

const FEATURES = [
  {
    icon: BarChart3,
    title: "IRS% Scoring",
    description:
      "Every stock scored on a 0-100 scale across value, momentum, quality, low-volatility, and insider factors — sector-adjusted.",
  },
  {
    icon: Brain,
    title: "PARA-DEBATE Analysis",
    description:
      "7 specialist agents argue bull and bear cases. A Head Analyst synthesises the debate into a single conviction rating.",
  },
  {
    icon: Shield,
    title: "Risk-First Research",
    description:
      "Regime detection, drawdown flags, and geopolitical scans keep you from walking into avoidable losses.",
  },
];

export default function VideoShowcase() {
  const [modalOpen, setModalOpen] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const sectionRef = useRef<HTMLElement>(null);

  // Intersection observer for scroll-triggered animations
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15 }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Lock body scroll when modal open
  useEffect(() => {
    if (modalOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [modalOpen]);

  const openModal = useCallback(() => setModalOpen(true), []);
  const closeModal = useCallback(() => setModalOpen(false), []);

  // Close on Escape
  useEffect(() => {
    if (!modalOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") closeModal();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [modalOpen, closeModal]);

  return (
    <>
      <section
        ref={sectionRef}
        className="relative w-full py-24 md:py-32 overflow-hidden"
        style={{ background: "var(--color-surface-deep)" }}
      >
        {/* Ambient glow */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[900px] h-[500px] bg-primary-fixed/3 rounded-full blur-[160px] pointer-events-none" />

        <div className="relative z-10 max-w-[1400px] mx-auto px-4 lg:px-16">
          {/* Header */}
          <div className="text-center mb-14">
            <span
              className={`inline-flex items-center gap-2 border border-tertiary-fixed/30 bg-surface-container-low px-4 py-2 font-mono text-[11px] font-bold tracking-[0.2em] uppercase text-tertiary-fixed-dim mb-6 transition-all duration-700 ${
                isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
              }`}
            >
              Demo
            </span>
            <h2
              className={`font-headline text-3xl md:text-5xl lg:text-6xl font-bold tracking-tight mb-4 transition-all duration-700 delay-100 ${
                isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
              }`}
            >
              See NeuralQuant in Action
            </h2>
            <p
              className={`text-text-muted max-w-2xl mx-auto text-lg leading-relaxed transition-all duration-700 delay-200 ${
                isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"
              }`}
            >
              Watch how IRS% scoring and PARA-DEBATE analysis work together to deliver
              institutional-grade equity research — in seconds.
            </p>
          </div>

          {/* Video area */}
          <div
            className={`relative mx-auto max-w-4xl mb-16 transition-all duration-700 delay-300 ${
              isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
            }`}
          >
            {/* Animated gradient border wrapper */}
            <div className="relative rounded-lg overflow-hidden p-[2px] bg-gradient-to-r from-primary-fixed/60 via-tertiary-fixed-dim/60 to-primary-fixed/60 animate-gradient-x">
              {/* Video container */}
              <div
                className="relative aspect-video rounded-lg overflow-hidden cursor-pointer group"
                onClick={openModal}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") openModal();
                }}
                aria-label="Play demo video"
              >
                {/* Animated gradient background */}
                <div className="absolute inset-0 bg-gradient-to-br from-surface-deep via-surface-container to-surface-deep">
                  {/* Subtle grid pattern overlay */}
                  <div className="absolute inset-0 opacity-10" style={{
                    backgroundImage: `
                      linear-gradient(rgba(0,255,178,0.3) 1px, transparent 1px),
                      linear-gradient(90deg, rgba(0,255,178,0.3) 1px, transparent 1px)
                    `,
                    backgroundSize: "40px 40px",
                  }} />
                  {/* Moving gradient orbs */}
                  <div className="absolute top-1/4 left-1/4 w-[300px] h-[300px] bg-primary-fixed/8 rounded-full blur-[80px] animate-float-slow" />
                  <div className="absolute bottom-1/4 right-1/4 w-[250px] h-[250px] bg-tertiary-fixed-dim/10 rounded-full blur-[80px] animate-float-slower" />
                  {/* Simulated UI elements */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-[80%] h-[70%] rounded border border-border-glow/30 bg-surface/20 backdrop-blur-sm p-4 md:p-6 flex flex-col gap-3">
                      {/* Fake header bar */}
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-error/60" />
                        <div className="w-2 h-2 rounded-full bg-warning/60" />
                        <div className="w-2 h-2 rounded-full bg-primary-fixed/60" />
                        <div className="ml-4 h-3 w-24 bg-surface-container/40 rounded" />
                        <div className="ml-auto h-3 w-16 bg-surface-container/40 rounded" />
                      </div>
                      {/* Fake content grid */}
                      <div className="flex-1 grid grid-cols-3 gap-2">
                        <div className="col-span-1 flex flex-col gap-2">
                          <div className="h-4 w-20 bg-primary-fixed/15 rounded" />
                          <div className="h-2 w-16 bg-surface-container/40 rounded" />
                          <div className="h-2 w-12 bg-surface-container/40 rounded" />
                          <div className="mt-auto h-10 w-full bg-primary-fixed/10 rounded border border-primary-fixed/20" />
                        </div>
                        <div className="col-span-2 flex flex-col gap-2">
                          <div className="h-4 w-32 bg-tertiary-fixed-dim/15 rounded" />
                          <div className="flex-1 rounded border border-border-glow/20 bg-surface-container/20 flex items-end px-2 pb-2 gap-1">
                            {/* Mini chart bars */}
                            {[35, 50, 42, 65, 55, 72, 60, 80, 68, 90, 75, 95].map((h, i) => (
                              <div
                                key={i}
                                className="flex-1 rounded-t bg-primary-fixed/30"
                                style={{ height: `${h}%` }}
                              />
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Play button overlay */}
                <div className="absolute inset-0 flex items-center justify-center bg-black/0 group-hover:bg-black/20 transition-colors duration-300">
                  <div className="relative">
                    {/* Pulse ring */}
                    <div className="absolute inset-0 rounded-full bg-primary-fixed/20 animate-ping-slow" />
                    {/* Play button */}
                    <div className="relative w-16 h-16 md:w-20 md:h-20 rounded-full bg-primary-fixed/90 backdrop-blur-sm border-2 border-primary-fixed flex items-center justify-center shadow-[0_0_30px_rgba(0,255,178,0.3)] group-hover:shadow-[0_0_50px_rgba(0,255,178,0.5)] group-hover:scale-110 transition-all duration-300">
                      <Play className="w-6 h-6 md:w-8 md:h-8 text-background fill-background ml-1" />
                    </div>
                  </div>
                </div>

                {/* Duration badge */}
                <div className="absolute bottom-4 right-4 px-2 py-1 bg-black/60 backdrop-blur-sm rounded font-mono text-[11px] text-text-primary">
                  3:42
                </div>
              </div>
            </div>

            {/* Watch Demo button below video */}
            <div className="mt-6 text-center">
              <button
                onClick={openModal}
                className="inline-flex items-center gap-2 bg-primary-fixed text-background font-mono text-[12px] font-bold tracking-[0.1em] uppercase px-8 py-4 hover:shadow-[0_0_30px_rgba(0,255,178,0.4)] transition-all duration-300"
              >
                <Play className="w-4 h-4 fill-background" />
                Watch Demo
              </button>
            </div>
          </div>

          {/* Feature callouts */}
          <div className="grid md:grid-cols-3 gap-4 md:gap-6">
            {FEATURES.map((feature, i) => (
              <div
                key={feature.title}
                className={`transition-all duration-700 ${
                  isVisible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-6"
                }`}
                style={{ transitionDelay: `${500 + i * 150}ms` }}
              >
                <GhostBorderCard hover>
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded bg-primary-fixed/10 border border-primary-fixed/20 flex items-center justify-center">
                      <feature.icon className="w-5 h-5 text-primary-fixed" />
                    </div>
                    <div>
                      <h3 className="font-headline font-bold text-lg text-primary mb-2">
                        {feature.title}
                      </h3>
                      <p className="text-sm text-text-muted leading-relaxed">
                        {feature.description}
                      </p>
                    </div>
                  </div>
                </GhostBorderCard>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 md:p-8"
          onClick={closeModal}
          role="dialog"
          aria-modal="true"
          aria-label="Demo video player"
        >
          {/* Backdrop */}
          <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" />

          {/* Modal content */}
          <div
            className="relative w-full max-w-5xl"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close button */}
            <button
              onClick={closeModal}
              className="absolute -top-12 right-0 md:top-2 md:-right-12 w-10 h-10 flex items-center justify-center text-text-muted hover:text-primary-fixed transition-colors"
              aria-label="Close video"
            >
              <X className="w-6 h-6" />
            </button>

            {/* Video frame */}
            <div className="relative aspect-video rounded-lg overflow-hidden border border-border-glow shadow-[0_0_60px_rgba(0,255,178,0.1)]">
              {/* Placeholder — replace src with real demo URL */}
              <div className="absolute inset-0 bg-gradient-to-br from-surface-deep via-surface-container to-surface-deep flex items-center justify-center">
                <div className="text-center">
                  <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-primary-fixed/20 border border-primary-fixed/30 flex items-center justify-center">
                    <Play className="w-8 h-8 text-primary-fixed ml-1" />
                  </div>
                  <p className="font-headline text-xl font-bold text-text-primary mb-2">
                    Demo Coming Soon
                  </p>
                  <p className="font-mono text-[11px] text-text-muted tracking-[0.1em] uppercase">
                    Full walkthrough video will be available here
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}