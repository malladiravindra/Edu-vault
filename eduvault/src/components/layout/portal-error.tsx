"use client";

import { ErrorState } from "@/components/shared/error-state";

/**
 * Error boundary content rendered inside the portal shell, so navigation
 * stays usable when a single page crashes.
 */
export function PortalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="rounded-xl border bg-card">
      <ErrorState
        title="This page failed to load"
        description={
          error.digest
            ? `An unexpected error occurred (ref: ${error.digest}). Try again, or contact support if it persists.`
            : "An unexpected error occurred. Try again, or contact support if it persists."
        }
        onRetry={reset}
      />
    </div>
  );
}
