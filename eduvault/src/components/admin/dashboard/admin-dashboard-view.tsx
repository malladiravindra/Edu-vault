"use client";

import Link from "next/link";
import { BookOpen, ClipboardList, DollarSign, KeyRound, UserCheck, Users } from "lucide-react";
import { formatCurrency, formatNumber } from "@/lib/format";
import { useAdminDashboard } from "@/hooks/use-reports";
import { useCurrentUser } from "@/hooks/use-auth";
import { PageHeader } from "@/components/shared/page-header";
import { StatCard } from "@/components/shared/stat-card";
import { ErrorState } from "@/components/shared/error-state";
import { ChartSkeleton, StatCardsSkeleton } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { CoursePopularityChart, RegistrationOverviewChart, RevenueOverviewChart } from "./dashboard-charts";
import { RecentActivity, RecentPayments, RecentRegistrations } from "./dashboard-recent";

const STATS_GRID = "stagger-children grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-6";

export function AdminDashboardView() {
  const dashboard = useAdminDashboard();
  const { data: user } = useCurrentUser();
  const firstName = user?.name.split(" ")[0];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        description={`Welcome back${firstName ? `, ${firstName}` : ""}. Here's what's happening across EduVault.`}
        actions={
          <>
            <Button variant="outline" nativeButton={false} render={<Link href="/admin/reports" />}>
              View reports
            </Button>
            <Button nativeButton={false} render={<Link href="/admin/registrations" />}>
              Review registrations
            </Button>
          </>
        }
      />

      {dashboard.isLoading ? (
        <>
          <StatCardsSkeleton count={6} className={STATS_GRID} />
          <div className="grid gap-6 lg:grid-cols-3">
            <ChartSkeleton className="lg:col-span-2" />
            <ChartSkeleton />
            <ChartSkeleton className="lg:col-span-3" />
          </div>
        </>
      ) : dashboard.error || !dashboard.data ? (
        <Card>
          <ErrorState
            title="We couldn't load the dashboard"
            error={dashboard.error}
            onRetry={() => dashboard.refetch()}
            retrying={dashboard.isFetching}
          />
        </Card>
      ) : (
        <>
          <section aria-label="Key metrics" className={STATS_GRID}>
            <StatCard
              label="Total Students"
              value={formatNumber(dashboard.data.stats.totalStudents)}
              trend={dashboard.data.stats.trends.totalStudents}
              icon={Users}
            />
            <StatCard
              label="Active Students"
              value={formatNumber(dashboard.data.stats.activeStudents)}
              trend={dashboard.data.stats.trends.activeStudents}
              icon={UserCheck}
            />
            <StatCard
              label="Pending Registrations"
              value={formatNumber(dashboard.data.stats.pendingRegistrations)}
              trend={dashboard.data.stats.trends.pendingRegistrations}
              invertTrend
              icon={ClipboardList}
            />
            <StatCard
              label="Active Courses"
              value={formatNumber(dashboard.data.stats.activeCourses)}
              trend={dashboard.data.stats.trends.activeCourses}
              icon={BookOpen}
            />
            <StatCard
              label="Active Access"
              value={formatNumber(dashboard.data.stats.activeAccess)}
              trend={dashboard.data.stats.trends.activeAccess}
              icon={KeyRound}
            />
            <StatCard
              label="Revenue"
              value={formatCurrency(dashboard.data.stats.revenue)}
              trend={dashboard.data.stats.trends.revenue}
              icon={DollarSign}
            />
          </section>

          <div className="grid gap-6 lg:grid-cols-3">
            <RevenueOverviewChart data={dashboard.data.revenueOverview} className="lg:col-span-2" />
            <CoursePopularityChart data={dashboard.data.coursePopularity} />
            <RegistrationOverviewChart data={dashboard.data.registrationsOverview} className="lg:col-span-3" />
          </div>
        </>
      )}

      <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
        <RecentRegistrations />
        <RecentPayments />
        <RecentActivity />
      </div>
    </div>
  );
}
