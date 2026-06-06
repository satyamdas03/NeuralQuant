"use client";

import { useEffect } from "react";

export default function ErrorBoundary({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to console for debugging
    // eslint-disable-next-line no-console
    console.error("[ErrorBoundary]", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 text-center">
      <div className="mb-6">
        <svg
          className="w-16 h-16 text-error mx-auto"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.205 16.5c-.77.833.192 2.5 1.732 2.5z"
          />
        </svg>
      </div>
      <h2 className="text-2xl font-semibold mb-2">Something went wrong</h2>
      <p className="text-on-surface-variant mb-6 max-w-md">
        We encountered an unexpected error while loading this page. This usually
        happens when the backend is warming up or data is being refreshed.
      </p>
      <div className="flex gap-3">
        <button
          onClick={reset}
          className="px-5 py-2.5 rounded-lg bg-primary text-on-primary font-medium hover:bg-primary/90 transition-colors"
        >
          Try Again
        </button>
        <button
          onClick={() => window.location.reload()}
          className="px-5 py-2.5 rounded-lg bg-surface-variant text-on-surface font-medium hover:bg-surface-variant/80 transition-colors"
        >
          Reload Page
        </button>
      </div>
      {process.env.NODE_ENV === "development" && (
        <pre className="mt-6 text-left text-xs bg-surface p-4 rounded-lg overflow-auto max-w-lg max-h-48 text-on-surface-variant">
          {error.message}
          {error.digest ? `\nDigest: ${error.digest}` : ""}
        </pre>
      )}
    </div>
  );
}
