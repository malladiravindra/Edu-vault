"use client";

import { ErrorState } from "@/components/shared/error-state";

/** Root error boundary for unexpected render errors outside the portals. */
export default function RootError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="flex min-h-dvh items-center justify-center p-6">
      <ErrorState
        title="Something went wrong"
        description={error.digest ? `An unexpected error occurred (ref: ${error.digest}).` : "An unexpected error occurred."}
        onRetry={reset}
      />
    </div>
  );
}
