"use client";

import { useMemo } from "react";
import { AlertTriangle, CircleDollarSign, Clock } from "lucide-react";
import type { Payment } from "@/types";
import { formatCurrency, formatNumber } from "@/lib/format";
import { usePayments } from "@/hooks/use-payments";
import { StatCard } from "@/components/shared/stat-card";
import { StatCardsSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/error-state";

/** Sample size for the all-time summary; independent of the table's filters and page. */
const SUMMARY_SAMPLE_SIZE = 500;

function summarize(payments: Payment[]) {
  let collected = 0;
  let successful = 0;
  let pendingAmount = 0;
  let pending = 0;
  let failed = 0;
  let refunded = 0;
  for (const p of payments) {
    if (p.status === "successful") {
      collected += p.amount;
      successful += 1;
    } else if (p.status === "pending") {
      pendingAmount += p.amount;
      pending += 1;
    } else if (p.status === "failed") {
      failed += 1;
    } else {
      refunded += 1;
    }
  }
  return { collected, successful, pendingAmount, pending, failed, refunded, currency: payments[0]?.currency ?? "USD" };
}

export function PaymentsSummary() {
  const query = usePayments({ pageSize: SUMMARY_SAMPLE_SIZE });
  const stats = useMemo(() => (query.data ? summarize(query.data.data) : null), [query.data]);

  if (query.isLoading) return <StatCardsSkeleton count={3} className="xl:grid-cols-3" />;
  if (query.error || !stats || !query.data) {
    return <ErrorState compact error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  const partial = query.data.total > query.data.data.length;
  const scope = partial ? `latest ${formatNumber(query.data.data.length)} payments` : "all time";

  return (
    <section aria-label="Payment summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <StatCard
        label="Total collected"
        value={formatCurrency(stats.collected, stats.currency)}
        icon={CircleDollarSign}
        hint={`${formatNumber(stats.successful)} successful payments · ${scope}`}
      />
      <StatCard
        label="Pending payments"
        value={formatNumber(stats.pending)}
        icon={Clock}
        hint={`${formatCurrency(stats.pendingAmount, stats.currency)} awaiting confirmation`}
      />
      <StatCard
        label="Failed / refunded"
        value={`${formatNumber(stats.failed)} / ${formatNumber(stats.refunded)}`}
        icon={AlertTriangle}
        hint={`Failed and refunded payments · ${scope}`}
        className="sm:col-span-2 xl:col-span-1"
      />
    </section>
  );
}
