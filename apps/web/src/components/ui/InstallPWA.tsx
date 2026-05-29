"use client";

import { useEffect, useState, useCallback } from "react";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const STORAGE_KEY = "pwa_dismissed_v1";
const IOS_TOOLTIP_KEY = "pwa_ios_tooltip_shown";

function isIOSSafari(): boolean {
  if (typeof window === "undefined") return false;
  const ua = window.navigator.userAgent;
  const isIOS = /iPad|iPhone|iPod/.test(ua);
  const isSafari = /Safari/.test(ua) && !/CriOS/.test(ua) && !/FxiOS/.test(ua);
  return isIOS && isSafari;
}

function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  return (
    window.matchMedia("(display-mode: standalone)").matches ||
    // iOS standalone detection
    (window.navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

export default function InstallPWA() {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [show, setShow] = useState(false);
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem(STORAGE_KEY) === "1";
  });
  const [isStandaloneMode] = useState(() => isStandalone());
  const [showIOSTooltip, setShowIOSTooltip] = useState(false);

  // Chrome/Edge/Android: beforeinstallprompt
  useEffect(() => {
    if (isStandaloneMode) return;
    if (dismissed) return;

    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      // Show after 30s of engagement
      const timer = setTimeout(() => {
        if (localStorage.getItem(STORAGE_KEY) !== "1") {
          setShow(true);
        }
      }, 30000);
      return () => clearTimeout(timer);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, [dismissed, isStandaloneMode]);

  // iOS Safari: no beforeinstallprompt — show manual tooltip once
  useEffect(() => {
    if (isStandaloneMode) return;
    if (!isIOSSafari()) return;
    if (localStorage.getItem(IOS_TOOLTIP_KEY) === "1") return;
    if (localStorage.getItem(STORAGE_KEY) === "1") return;

    const timer = setTimeout(() => {
      setShowIOSTooltip(true);
      localStorage.setItem(IOS_TOOLTIP_KEY, "1");
    }, 35000);
    return () => clearTimeout(timer);
  }, [isStandaloneMode]);

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
    localStorage.setItem(STORAGE_KEY, "1");
  }, []);

  const dismissIOS = useCallback(() => {
    setShowIOSTooltip(false);
  }, []);

  if (!show && !showIOSTooltip) return null;

  // iOS Safari tooltip
  if (showIOSTooltip) {
    return (
      <div className="fixed bottom-20 left-4 right-4 z-50 sm:left-auto sm:right-4 sm:w-80">
        <div className="bg-[#0f0f1a] border border-[#00ffb2]/30 rounded-lg p-4 shadow-lg shadow-[#00ffb2]/10">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-white">
                Add QuantAlpha to Home Screen
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Tap <strong>Share</strong> → <strong>Add to Home Screen</strong> to install.
              </p>
            </div>
            <button
              onClick={dismissIOS}
              className="text-gray-500 hover:text-gray-300 text-lg leading-none"
              aria-label="Dismiss"
            >
              ×
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Chrome/Edge/Android install banner
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
