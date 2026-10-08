"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookX, CalendarClock, Clock, FileText, Lock, User } from "lucide-react";
import type { StudentCourse } from "@/types";
import { getCourseCta } from "@/lib/course-access";
import { formatAccessDuration, formatDate, formatPrice } from "@/lib/format";
import { useStudentCourse } from "@/hooks/use-courses";
import { usePublishedResources } from "@/hooks/use-resources";
import { useBreadcrumbLabel } from "@/components/layout/breadcrumbs";
import { CourseCover } from "@/components/shared/course-cover";
import { ResourceCard } from "@/components/shared/resource-card";
import { AccessStatusBadge } from "@/components/shared/status-badge";
import { DetailSkeleton, ListSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { isNotFoundError, viewerHref } from "../shared/utils";
import { ExpiryNote } from "../shared/expiry-note";
import { RequestAccessDialog } from "./request-access-dialog";

export function CourseDetailsView({ id }: { id: string }) {
  const query = useStudentCourse(id);
  const course = query.data;
  useBreadcrumbLabel(id, course?.name);

  if (query.isLoading) return <DetailSkeleton />;

  if (query.error || !course) {
    if (isNotFoundError(query.error)) {
      return (
        <div className="rounded-xl border bg-card">
          <EmptyState
            icon={BookX}
            title="Course not found"
            description="This course may have been removed or is no longer available."
            action={
              <Button variant="outline" size="sm" nativeButton={false} render={<Link href="/student/courses" />}>
                <ArrowLeft aria-hidden />
                Back to courses
              </Button>
            }
          />
        </div>
      );
    }
    return (
      <div className="rounded-xl border bg-card">
        <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
      </div>
    );
  }

  return <CourseDetails course={course} />;
}

function CourseDetails({ course }: { course: StudentCourse }) {
  const resources = usePublishedResources(course.id);
  const [requestOpen, setRequestOpen] = useState(false);
  const isActive = course.access === "active";

  return (
    <div className="space-y-6">
      <Link
        href="/student/courses"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground focus-visible:underline focus-visible:outline-none"
      >
        <ArrowLeft className="size-4" aria-hidden />
        All courses
      </Link>

      <section className="overflow-hidden rounded-xl border bg-card">
        <CourseCover
          courseId={course.id}
          name={course.name}
          category={course.category}
          imageUrl={course.imageUrl}
          variant="banner"
          className="h-40 md:h-52"
        />
        <div className="flex flex-col gap-3 p-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0 space-y-2">
            <h1 className="text-2xl font-semibold tracking-tight text-balance">{course.name}</h1>
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
              <span>{course.category}</span>
              <span className="inline-flex items-center gap-1.5">
                <User className="size-3.5" aria-hidden />
                {course.instructor}
              </span>
            </div>
          </div>
          <AccessStatusBadge status={course.access} className="w-fit shrink-0" />
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                <h2>About this course</h2>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm leading-relaxed whitespace-pre-line text-muted-foreground">{course.description}</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                <h2>What&apos;s included</h2>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {!isActive && (
                <p className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Lock className="size-3.5" aria-hidden />
                  Resources unlock once your access is active.
                </p>
              )}
              {resources.isLoading ? (
                <ListSkeleton rows={3} />
              ) : resources.error ? (
                <ErrorState
                  compact
                  error={resources.error}
                  onRetry={() => resources.refetch()}
                  retrying={resources.isFetching}
                />
              ) : !resources.data?.length ? (
                <EmptyState
                  compact
                  icon={FileText}
                  title="No resources yet"
                  description="The instructor hasn't published any materials for this course yet."
                />
              ) : (
                <ul className="space-y-3">
                  {resources.data.map((r) => (
                    <li key={r.id}>
                      <ResourceCard
                        resource={r}
                        locked={!isActive}
                        action={
                          isActive ? (
                            <Button
                              size="sm"
                              variant="outline"
                              nativeButton={false}
                              render={<Link href={viewerHref(course.id, r.id)} />}
                            >
                              Open
                            </Button>
                          ) : undefined
                        }
                      />
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <aside className="lg:sticky lg:top-20 lg:self-start">
          <Card>
            <CardContent className="space-y-5">
              <div>
                <p className="text-sm text-muted-foreground">Price</p>
                <p className="text-3xl font-semibold tracking-tight tabular-nums">
                  {formatPrice(course.price, course.currency)}
                </p>
              </div>
              <Separator />
              <dl className="space-y-3 text-sm">
                <SummaryRow icon={Clock} label="Access duration" value={formatAccessDuration(course.accessDurationDays)} />
                <SummaryRow icon={FileText} label="Resources" value={`${course.resourceCount}`} />
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-muted-foreground">Access status</dt>
                  <dd>
                    <AccessStatusBadge status={course.access} />
                  </dd>
                </div>
                {course.expiresAt && (
                  <SummaryRow
                    icon={CalendarClock}
                    label={course.access === "expired" ? "Expired" : "Expires"}
                    value={formatDate(course.expiresAt)}
                  />
                )}
              </dl>
              {course.access === "active" && course.expiresAt && <ExpiryNote expiresAt={course.expiresAt} warnOnly />}
              <CourseCtaBlock course={course} onRequest={() => setRequestOpen(true)} />
            </CardContent>
          </Card>
        </aside>
      </div>

      <RequestAccessDialog course={course} open={requestOpen} onOpenChange={setRequestOpen} />
    </div>
  );
}

function SummaryRow({ icon: Icon, label, value }: { icon: typeof Clock; label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="inline-flex items-center gap-2 text-muted-foreground">
        <Icon className="size-4" aria-hidden />
        {label}
      </dt>
      <dd className="font-medium tabular-nums">{value}</dd>
    </div>
  );
}

function CourseCtaBlock({ course, onRequest }: { course: StudentCourse; onRequest: () => void }) {
  const cta = getCourseCta(course.id, course.access);

  if (cta.kind === "status") {
    return (
      <div className="space-y-2">
        <Button variant="outline" className="w-full" aria-disabled="true" disabled>
          {cta.detailLabel}
        </Button>
        <p className="text-center text-xs text-muted-foreground">
          {course.requestedAt ? `Submitted ${formatDate(course.requestedAt)}. ` : ""}
          Your request is being reviewed; we&apos;ll notify you as soon as there&apos;s an update.
        </p>
      </div>
    );
  }

  if (cta.disabled) {
    return (
      <div className="space-y-2">
        <Button variant={cta.variant} className="w-full" disabled>
          {cta.detailLabel}
        </Button>
        <p className="text-center text-xs text-muted-foreground">Contact support to renew your access.</p>
      </div>
    );
  }

  if (cta.href) {
    return (
      <Button variant={cta.variant} className="w-full" nativeButton={false} render={<Link href={cta.href} />}>
        {cta.detailLabel}
      </Button>
    );
  }

  return (
    <Button variant={cta.variant} className="w-full" onClick={onRequest}>
      {cta.detailLabel}
    </Button>
  );
}
