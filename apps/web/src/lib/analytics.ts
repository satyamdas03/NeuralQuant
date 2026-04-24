const PLAUSIBLE_DOMAIN = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;

export function trackEvent(name: string, props?: Record<string, string>) {
  if (typeof window === "undefined" || !PLAUSIBLE_DOMAIN) return;
  window.plausible?.(name, { props });
}

declare global {
  interface Window {
    plausible?: (event: string, options?: { props?: Record<string, string> }) => void;
  }
}