"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { trackEvent, EVENT } from "@/lib/analytics";

/**
 * Mount once in root layout. Tracks pageviews on every route change
 * and sends them to Plausible.
 *
 * Plausible auto-tracks pageviews via its script tag, but SPA navigations
 * need an explicit call. This component fires trackEvent on every pathname
 * change so dashboard, screener, etc. all register.
 */
export default function AnalyticsRouteTracker() {
  const pathname = usePathname();

  useEffect(() => {
    // Small delay to let title settle
    const t = setTimeout(() => {
      trackEvent(EVENT.PAGEVIEW, { path: pathname });
    }, 100);
    return () => clearTimeout(t);
  }, [pathname]);

  return null;
}