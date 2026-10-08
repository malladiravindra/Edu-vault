"use client";

import { BookOpenCheck, CheckCircle2, Clock, Gauge } from "lucide-react";
import { formatDuration } from "@/lib/format";
import { useLearningHistory } from "@/hooks/use-learning";
import { StatCard } from "@/components/shared/stat-card";
import { StatCardsSkeleton } from "@/components/shared/loading-skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { Card } from "@/components/ui/card";

/** Lifetime learning totals, independent of the table filters. */
export function LearningSummary() {
  const query = useLearningHistory({ pageSize: 500 });

  if (query.isLoading) return <StatCardsSkeleton count={4} />;
  if (query.error) {
    return (
      <Card className="py-0">
        <ErrorState
          compact
          title="We couldn't load your learning summary"
          error={query.error}
          onRetry={() => query.refetch()}
          retrying={query.isFetching}
        />
      </Card>
    );
  }

  const items = query.data?.data ?? [];
  const totalMinutes = items.reduce((sum, a) => sum + a.timeSpentMinutes, 0);
  const avgProgress = items.length ? Math.round(items.reduce((sum, a) => sum + a.progress, 0) / items.length) : 0;
  const completed = items.filter((a) => a.progress >= 100).length;

  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard label="Total time spent" value={formatDuration(totalMinutes)} icon={Clock} hint="Across all resources" />
      <StatCard label="Resources studied" value={items.length} icon={BookOpenCheck} />
      <StatCard label="Average progress" value={`${avgProgress}%`} icon={Gauge} />
      <StatCard
        label="Completed resources"
        value={completed}
        icon={CheckCircle2}
        hint={items.length ? `of ${items.length} studied` : undefined}
      />
    </div>
  );
}
