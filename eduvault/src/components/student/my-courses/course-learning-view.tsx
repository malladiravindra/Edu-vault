"use client";

import { useMemo } from "react";
import Link from "next/link";
import { ArrowLeft, BookX, FileText, Lock } from "lucide-react";
import type { LearningActivity, StudentCourse } from "@/types";
import { getCourseCta } from "@/lib/course-access";
import { useStudentCourse } from "@/hooks/use-courses";
import { usePublishedResources } from "@/hooks/use-resources";
import { useLearningHistory } from "@/hooks/use-learning";
import { useBreadcrumbLabel } from "@/components/layout/breadcrumbs";
import { PageHeader } from "@/components/shared/page-header";
import { ResourceCard } from "@/components/shared/resource-card";
import { AccessStatusBadge } from "@/components/shared/status-badge";
import { ProgressBar } from "@/components/shared/progress-bar";
import { DetailSkeleton, ListSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CourseThumbnail } from "../shared/course-thumbnail";
import { ExpiryNote } from "../shared/expiry-note";
import { isNotFoundError, viewerHref } from "../shared/utils";

const backLink = (
  <Link
    href="/student/my-courses"
    className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground focus-visible:underline focus-visible:outline-none"
  >
    <ArrowLeft className="size-4" aria-hidden />
    My courses
  </Link>
);

export function CourseLearningView({ id }: { id: string }) {
  const query = useStudentCourse(id);
  const course = query.data;
  useBreadcrumbLabel(id, course?.name);

  if (query.isLoading) return <DetailSkeleton />;

  if (query.error || !course) {
    return (
      <div className="space-y-6">
        {backLink}
        <div className="rounded-xl border bg-card">
          {isNotFoundError(query.error) ? (
            <EmptyState
              icon={BookX}
              title="Course not found"
              description="This course may have been removed or is no longer available."
            />
          ) : (
            <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={backLink}
        title={course.name}
        description={`${course.category} · ${course.instructor}`}
        actions={<AccessStatusBadge status={course.access} />}
      />
      {course.access === "active" ? <ActiveCourse course={course} /> : <LockedCourse course={course} />}
    </div>
  );
}

function ActiveCourse({ course }: { course: StudentCourse }) {
  const resources = usePublishedResources(course.id);
  const history = useLearningHistory({ courseId: course.id, pageSize: 100 });

  const progressByResource = useMemo(() => {
    const map = new Map<string, LearningActivity>();
    for (const a of history.data?.data ?? []) {
      const prev = map.get(a.resourceId);
      if (!prev || prev.lastAccessedAt < a.lastAccessedAt) map.set(a.resourceId, a);
    }
    return map;
  }, [history.data]);

  return (
    <>
      <Card>
        <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <CourseThumbnail course={course} className="hidden sm:block" />
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="font-medium">Course progress</span>
              <ExpiryNote expiresAt={course.expiresAt} />
            </div>
            <ProgressBar value={course.progress} size="md" label="Course progress" />
          </div>
        </CardContent>
      </Card>

      <section className="space-y-3" aria-labelledby="resources-heading">
        <h2 id="resources-heading" className="text-base font-semibold">
          Course resources
        </h2>
        {resources.isLoading ? (
          <ListSkeleton rows={4} />
        ) : resources.error ? (
          <div className="rounded-xl border bg-card">
            <ErrorState error={resources.error} onRetry={() => resources.refetch()} retrying={resources.isFetching} />
          </div>
        ) : !resources.data?.length ? (
          <div className="rounded-xl border border-dashed bg-card">
            <EmptyState
              icon={FileText}
              title="No resources yet"
              description="Materials will appear here as soon as the instructor publishes them."
            />
          </div>
        ) : (
          <ul className="space-y-3">
            {resources.data.map((r) => {
              const activity = progressByResource.get(r.id);
              const started = Boolean(activity && activity.progress > 0);
              return (
                <li key={r.id}>
                  <ResourceCard
                    resource={r}
                    progress={activity?.progress ?? 0}
                    action={
                      <Button
                        size="sm"
                        variant={started ? "default" : "outline"}
                        nativeButton={false}
                        render={<Link href={viewerHref(course.id, r.id, activity?.lastPage)} />}
                        aria-label={`${started ? "Continue" : "Open"} ${r.name}`}
                      >
                        {started ? "Continue" : "Open"}
                      </Button>
                    }
                  />
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </>
  );
}

const LOCKED_TITLE: Record<Exclude<StudentCourse["access"], "active">, string> = {
  none: "This course is locked",
  pending: "Access request pending",
  payment_required: "Payment required",
  expired: "Access expired",
  suspended: "Access suspended",
};

const LOCKED_COPY: Record<Exclude<StudentCourse["access"], "active">, string> = {
  none: "You don't have access to this course yet. Request access to unlock its resources.",
  pending: "Your access request is being reviewed. We'll notify you as soon as it's approved.",
  payment_required: "Your request was approved. Complete payment to unlock the course resources.",
  expired: "Your access to this course has expired. Contact support to renew.",
  suspended: "Your access to this course has been suspended. Contact support for help.",
};

function LockedCourse({ course }: { course: StudentCourse }) {
  const access = course.access === "active" ? "none" : course.access;
  const cta = getCourseCta(course.id, access);
  // Request flow lives on the course details page; send the student there.
  const href = cta.kind === "request" || cta.kind === "status" ? `/student/courses/${course.id}` : cta.href;

  return (
    <div className="rounded-xl border bg-card">
      <EmptyState
        icon={Lock}
        title={LOCKED_TITLE[access]}
        description={LOCKED_COPY[access]}
        action={
          href && !cta.disabled ? (
            <Button size="sm" variant={cta.variant} nativeButton={false} render={<Link href={href} />}>
              {cta.kind === "request" ? "View course" : cta.cardLabel}
            </Button>
          ) : (
            <Button size="sm" variant="secondary" disabled>
              {cta.cardLabel}
            </Button>
          )
        }
      />
    </div>
  );
}
