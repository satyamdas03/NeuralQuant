"use client";

import { useEffect, useState, useCallback } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

export default function InstallPWA() {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [show, setShow] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      // Show after 30s of engagement, only if not installed
      const timer = setTimeout(() => {
        if (!dismissed) setShow(true);
      }, 30000);
      return () => clearTimeout(timer);
    };
    window.addEventListener("beforeinstallprompt", handler);

    // Hide if already standalone
    if (window.matchMedia("(display-mode: standalone)").matches) {
      setShow(false);
    }

    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, [dismissed]);

  const install = useCallback(async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setShow(false);
    }
    setDeferredPrompt(null);
  }, [deferredPrompt]);

  const dismiss = useCallback(() => {
    setShow(false);
    setDismissed(true);
  }, []);

  if (!show) return null;

  return (
    <div className="fixed bottom-20 left-4 right-4 z-50 sm:left-auto sm:right-4 sm:w-80">
      <div className="bg-[#0f0f1a] border border-[#00ffb2]/30 rounded-lg p-4 shadow-lg shadow-[#00ffb2]/10">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-white">
              Add QuantAlpha to Home Screen
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Quick access to AI-powered stock research
            </p>
          </div>
          <button
            onClick={dismiss}
            className="text-gray-500 hover:text-gray-300 text-lg leading-none"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
        <button
          onClick={install}
          className="mt-3 w-full bg-[#00ffb2] text-black font-semibold text-sm py-2 rounded-md hover:bg-[#00ffb2]/90 transition-colors"
        >
          Install
        </button>
      </div>
    </div>
  );
}
