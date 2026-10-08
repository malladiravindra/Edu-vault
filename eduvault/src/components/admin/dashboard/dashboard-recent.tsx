"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowRight, ClipboardList, CreditCard, ScrollText } from "lucide-react";
import { formatCurrency, formatRelative } from "@/lib/format";
import { useRegistrations } from "@/hooks/use-registrations";
import { usePayments } from "@/hooks/use-payments";
import { useAuditLogs } from "@/hooks/use-audit-logs";
import { ChartCard } from "@/components/shared/chart-card";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Skeleton } from "@/components/ui/skeleton";
import { PaymentStatusBadge, RegistrationStatusBadge } from "@/components/shared/status-badge";
import { UserCell } from "@/components/shared/user-avatar";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface QueryLike<T> {
  data?: { data: T[] };
  isLoading: boolean;
  isFetching: boolean;
  error: unknown;
  refetch: () => unknown;
}

interface PanelProps<T> {
  title: string;
  description: string;
  href: string;
  query: QueryLike<T>;
  rows: number;
  emptyIcon: LucideIcon;
  emptyTitle: string;
  renderItem: (item: T) => ReactNode;
  getKey: (item: T) => string;
  listClassName?: string;
}

function PanelSkeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-4" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="size-7 rounded-full" />
          <div className="flex-1 space-y-1.5">
            <Skeleton className="h-3.5 w-1/2" />
            <Skeleton className="h-3 w-2/3" />
          </div>
          <Skeleton className="h-5 w-16" />
        </div>
      ))}
    </div>
  );
}

function RecentPanel<T>({
  title,
  description,
  href,
  query,
  rows,
  emptyIcon,
  emptyTitle,
  renderItem,
  getKey,
  listClassName,
}: PanelProps<T>) {
  const items = query.data?.data ?? [];
  return (
    <ChartCard
      title={title}
      description={description}
      action={
        <Button variant="ghost" size="sm" nativeButton={false} render={<Link href={href} />}>
          View all
          <ArrowRight aria-hidden />
        </Button>
      }
    >
      {query.isLoading ? (
        <PanelSkeleton rows={rows} />
      ) : query.error ? (
        <ErrorState compact error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
      ) : items.length === 0 ? (
        <EmptyState compact icon={emptyIcon} title={emptyTitle} />
      ) : (
        <ul className={cn("divide-y", listClassName)}>
          {items.map((item) => (
            <li key={getKey(item)} className="py-3 first:pt-0 last:pb-0">
              {renderItem(item)}
            </li>
          ))}
        </ul>
      )}
    </ChartCard>
  );
}

export function RecentRegistrations() {
  const query = useRegistrations({ pageSize: 5 });
  return (
    <RecentPanel
      title="Recent registrations"
      description="Latest course access requests"
      href="/admin/registrations"
      query={query}
      rows={5}
      emptyIcon={ClipboardList}
      emptyTitle="No registrations yet"
      getKey={(r) => r.id}
      renderItem={(r) => (
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <UserCell name={r.studentName} email={r.courseName} />
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <RegistrationStatusBadge status={r.status} />
            <time dateTime={r.createdAt} className="text-xs text-muted-foreground">
              {formatRelative(r.createdAt)}
            </time>
          </div>
        </div>
      )}
    />
  );
}

export function RecentPayments() {
  const query = usePayments({ pageSize: 5 });
  return (
    <RecentPanel
      title="Recent payments"
      description="Latest transactions"
      href="/admin/payments"
      query={query}
      rows={5}
      emptyIcon={CreditCard}
      emptyTitle="No payments yet"
      getKey={(p) => p.id}
      renderItem={(p) => (
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <UserCell name={p.studentName} email={p.courseName} />
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <span className="text-sm font-medium tabular-nums">{formatCurrency(p.amount, p.currency)}</span>
            <PaymentStatusBadge status={p.status} />
          </div>
        </div>
      )}
    />
  );
}

export function RecentActivity() {
  const query = useAuditLogs({ pageSize: 6 });
  return (
    <RecentPanel
      title="Recent activity"
      description="Latest audit events"
      href="/admin/audit-logs"
      query={query}
      rows={6}
      emptyIcon={ScrollText}
      emptyTitle="No activity yet"
      getKey={(l) => l.id}
      listClassName="divide-y-0"
      renderItem={(log) => (
        <div className="relative flex gap-3 pl-1">
          <span
            aria-hidden
            className={cn(
              "mt-1.5 size-2 shrink-0 rounded-full ring-4 ring-card",
              log.status === "success" ? "bg-success" : log.status === "warning" ? "bg-warning" : "bg-destructive",
            )}
          />
          <div className="min-w-0 flex-1 space-y-0.5">
            <div className="flex items-baseline justify-between gap-2">
              <p className="truncate text-sm font-medium">{log.action}</p>
              <time dateTime={log.createdAt} className="shrink-0 text-xs text-muted-foreground">
                {formatRelative(log.createdAt)}
              </time>
            </div>
            <p className="line-clamp-2 text-xs text-muted-foreground">{log.description}</p>
            <p className="text-xs text-muted-foreground/80">{log.userName}</p>
          </div>
        </div>
      )}
    />
  );
}
