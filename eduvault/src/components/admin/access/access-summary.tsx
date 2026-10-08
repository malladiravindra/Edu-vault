"use client";

import type { AccessStatus } from "@/types";
import { ACCESS_STATUS } from "@/lib/constants";
import { useAccessSummary } from "@/hooks/use-access";
import { ErrorState } from "@/components/shared/error-state";
import { StatCardsSkeleton } from "@/components/shared/loading-skeleton";
import { cn } from "@/lib/utils";

export const ACCESS_STATUS_ORDER: AccessStatus[] = ["active", "pending", "payment_required", "expired", "suspended"];

const DOT_CLASS: Record<AccessStatus, string> = {
  active: "bg-success",
  pending: "bg-warning",
  payment_required: "bg-info",
  expired: "bg-muted-foreground/60",
  suspended: "bg-destructive",
};

interface AccessSummaryProps {
  selected: AccessStatus | undefined;
  onSelect: (status: AccessStatus | undefined) => void;
}

/** Per-status counts; each tile toggles the table's status filter. */
export function AccessSummary({ selected, onSelect }: AccessSummaryProps) {
  const query = useAccessSummary();

  if (query.isLoading) {
    return <StatCardsSkeleton count={5} className="grid-cols-2 sm:grid-cols-3 xl:grid-cols-5" />;
  }
  if (query.error || !query.data) {
    return <ErrorState compact error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const counts = query.data;
  return (
    <div role="group" aria-label="Filter by access status" className="grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
      {ACCESS_STATUS_ORDER.map((status) => {
        const pressed = selected === status;
        return (
          <button
            key={status}
            type="button"
            aria-pressed={pressed}
            onClick={() => onSelect(pressed ? undefined : status)}
            className={cn(
              "rounded-xl border bg-card px-4 py-3 text-left transition-colors outline-none hover:bg-accent/50 focus-visible:ring-3 focus-visible:ring-ring/50",
              pressed && "border-primary ring-1 ring-primary bg-primary/5 hover:bg-primary/5",
            )}
          >
            <span className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
              <span className={cn("size-2 rounded-full", DOT_CLASS[status])} aria-hidden />
              {ACCESS_STATUS[status].label}
            </span>
            <span className="mt-1 block text-2xl font-semibold tracking-tight tabular-nums">{counts[status]}</span>
          </button>
        );
      })}
    </div>
  );
}
