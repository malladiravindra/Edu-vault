"use client";

import { useState } from "react";
import Link from "next/link";
import { BookOpen, Clock, CreditCard, History, type LucideIcon } from "lucide-react";
import type { StudentCourse } from "@/types";
import { useMyCourses } from "@/hooks/use-courses";
import { PageHeader } from "@/components/shared/page-header";
import { CourseCover } from "@/components/shared/course-cover";
import { AccessStatusBadge } from "@/components/shared/status-badge";
import { ProgressBar } from "@/components/shared/progress-bar";
import { CardGridSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ExpiryNote } from "../shared/expiry-note";

type TabKey = "active" | "pending" | "payment_required" | "expired";

interface TabMeta {
  label: string;
  emptyTitle: string;
  emptyDescription: string;
  icon: LucideIcon;
  /** Suspended access is grouped with expired: both need support to restore. */
  matches: (c: StudentCourse) => boolean;
}

const TABS: Record<TabKey, TabMeta> = {
  active: {
    label: "Active",
    emptyTitle: "No active courses",
    emptyDescription: "Courses you have access to will appear here.",
    icon: BookOpen,
    matches: (c) => c.access === "active",
  },
  pending: {
    label: "Pending",
    emptyTitle: "No pending requests",
    emptyDescription: "Requests awaiting review will appear here.",
    icon: Clock,
    matches: (c) => c.access === "pending",
  },
  payment_required: {
    label: "Payment Required",
    emptyTitle: "Nothing awaiting payment",
    emptyDescription: "Approved courses that need payment will appear here.",
    icon: CreditCard,
    matches: (c) => c.access === "payment_required",
  },
  expired: {
    label: "Expired",
    emptyTitle: "No expired courses",
    emptyDescription: "Courses whose access has ended or been suspended will appear here.",
    icon: History,
    matches: (c) => c.access === "expired" || c.access === "suspended",
  },
};

const TAB_KEYS = Object.keys(TABS) as TabKey[];

export function MyCoursesView() {
  const query = useMyCourses();
  const [tab, setTab] = useState<TabKey>("active");
  const courses = query.data ?? [];

  return (
    <div className="space-y-6">
      <PageHeader
        title="My Courses"
        description="Track your enrolled courses, pending requests and access status."
        actions={
          <Button variant="outline" nativeButton={false} render={<Link href="/student/courses" />}>
            Browse courses
          </Button>
        }
      />

      {query.isLoading ? (
        <CardGridSkeleton count={3} />
      ) : query.error ? (
        <div className="rounded-xl border bg-card">
          <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
        </div>
      ) : (
        <Tabs value={tab} onValueChange={(v) => setTab(v as TabKey)}>
          <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
            <TabsList variant="line">
              {TAB_KEYS.map((key) => (
                <TabsTrigger key={key} value={key}>
                  {TABS[key].label}
                  <span className="ml-1.5 rounded-full bg-muted px-1.5 text-xs text-muted-foreground tabular-nums">
                    {courses.filter(TABS[key].matches).length}
                  </span>
                </TabsTrigger>
              ))}
            </TabsList>
          </div>
          {TAB_KEYS.map((key) => {
            const items = courses.filter(TABS[key].matches);
            const meta = TABS[key];
            return (
              <TabsContent key={key} value={key} className="pt-4">
                {items.length === 0 ? (
                  <div className="rounded-xl border border-dashed bg-card">
                    <EmptyState
                      icon={meta.icon}
                      title={meta.emptyTitle}
                      description={meta.emptyDescription}
                      action={
                        <Button size="sm" nativeButton={false} render={<Link href="/student/courses" />}>
                          Browse courses
                        </Button>
                      }
                    />
                  </div>
                ) : (
                  <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                    {items.map((course) => (
                      <MyCourseCard key={course.id} course={course} />
                    ))}
                  </div>
                )}
              </TabsContent>
            );
          })}
        </Tabs>
      )}
    </div>
  );
}

function MyCourseCard({ course }: { course: StudentCourse }) {
  return (
    <Card className="gap-0 overflow-hidden pt-0">
      <CourseCover
        courseId={course.id}
        name={course.name}
        category={course.category}
        imageUrl={course.imageUrl}
        className="aspect-[16/7]"
      />
      <CardContent className="flex flex-1 flex-col gap-3 pt-4">
        <div className="flex items-start justify-between gap-3">
          <h2 className="leading-snug font-semibold">
            <Link
              href={`/student/courses/${course.id}`}
              className="hover:underline focus-visible:underline focus-visible:outline-none"
            >
              {course.name}
            </Link>
          </h2>
          <AccessStatusBadge status={course.access} className="shrink-0" />
        </div>
        {course.access === "active" && <ProgressBar value={course.progress} label={`${course.name} progress`} />}
        <div className="mt-auto">
          {course.access === "active" || course.access === "expired" ? (
            <ExpiryNote expiresAt={course.expiresAt} />
          ) : course.access === "pending" ? (
            <span className="text-xs text-muted-foreground">Awaiting admin review</span>
          ) : course.access === "payment_required" ? (
            <span className="text-xs text-muted-foreground">Approved — complete payment to unlock</span>
          ) : (
            <span className="text-xs text-muted-foreground">Access suspended — contact support</span>
          )}
        </div>
      </CardContent>
      <CardFooter className="mt-4 justify-end border-t bg-muted/30 py-3">
        <MyCourseAction course={course} />
      </CardFooter>
    </Card>
  );
}

function MyCourseAction({ course }: { course: StudentCourse }) {
  switch (course.access) {
    case "active":
      return (
        <Button size="sm" nativeButton={false} render={<Link href={`/student/my-courses/${course.id}`} />}>
          Continue
        </Button>
      );
    case "pending":
      return (
        <Button size="sm" variant="outline" nativeButton={false} render={<Link href={`/student/courses/${course.id}`} />}>
          View status
        </Button>
      );
    case "payment_required":
      return (
        <Button
          size="sm"
          nativeButton={false}
          render={<Link href={`/student/payments/checkout?course=${course.id}`} />}
        >
          Proceed to Payment
        </Button>
      );
    default:
      return (
        <Button size="sm" variant="secondary" disabled title="Contact support to renew">
          Renew
        </Button>
      );
  }
}
