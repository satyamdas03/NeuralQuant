"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // eslint-disable-next-line no-console
    console.error("[GlobalError]", error);
  }, [error]);

  return (
    <html>
      <body className="bg-background text-on-surface">
        <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center">
          <div className="mb-6">
            <svg
              className="w-20 h-20 text-error mx-auto"
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
          <h1 className="text-3xl font-bold mb-2">NeuralQuant</h1>
          <h2 className="text-xl font-semibold mb-2">Application Error</h2>
          <p className="text-on-surface-variant mb-8 max-w-md">
            We&apos;re having trouble loading the app. The backend may be warming up
            after a deployment. Please try reloading in a few moments.
          </p>
          <div className="flex gap-3">
            <button
              onClick={reset}
              className="px-6 py-3 rounded-lg bg-primary text-on-primary font-medium hover:bg-primary/90 transition-colors"
            >
              Try Again
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-6 py-3 rounded-lg bg-surface-variant text-on-surface font-medium hover:bg-surface-variant/80 transition-colors"
            >
              Reload Page
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
