"use client";

import Link from "next/link";
import { ArrowLeft, BookX, CalendarClock, FileText, Tag, Users } from "lucide-react";
import type { Course } from "@/types";
import { formatAccessDuration, formatDateTime, formatNumber, formatPrice } from "@/lib/format";
import { notify } from "@/lib/toast";
import { useCourse, useUpdateCourse } from "@/hooks/use-courses";
import { useCourseResources } from "@/hooks/use-resources";
import { useBreadcrumbLabel } from "@/components/layout/breadcrumbs";
import { CourseCover } from "@/components/shared/course-cover";
import { CourseStatusBadge, ResourceStatusBadge } from "@/components/shared/status-badge";
import { DetailSkeleton, ListSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { ResourceCard } from "@/components/shared/resource-card";
import { StatCard } from "@/components/shared/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CourseForm } from "./course-form";
import { ACCESS_MODEL_SHORT, courseToFormValues } from "./course-schema";
import { CourseStatusDialog, getCourseStatusActions, useCourseStatusDialog } from "./course-status-dialog";
import { isNotFoundError } from "./course-utils";

const RESOURCE_PREVIEW_COUNT = 5;

export function CourseDetailView({ id }: { id: string }) {
  const query = useCourse(id);
  const course = query.data;
  useBreadcrumbLabel(id, course?.name);

  if (query.isLoading) return <DetailSkeleton />;

  if (query.error || !course) {
    if (isNotFoundError(query.error)) {
      return (
        <EmptyState
          icon={BookX}
          title="Course not found"
          description="This course may have been removed, or the link is incorrect."
          action={
            <Button variant="outline" nativeButton={false} render={<Link href="/admin/courses" />}>
              <ArrowLeft />
              Back to courses
            </Button>
          }
        />
      );
    }
    return <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  }

  return <CourseDetail course={course} />;
}

function CourseDetail({ course }: { course: Course }) {
  const update = useUpdateCourse(course.id);
  const statusDialog = useCourseStatusDialog();

  return (
    <div className="space-y-6">
      <Link
        href="/admin/courses"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden />
        Courses
      </Link>

      <div className="overflow-hidden rounded-xl border bg-card">
        <CourseCover
          courseId={course.id}
          name={course.name}
          category={course.category}
          imageUrl={course.imageUrl}
          variant="banner"
          className="aspect-[4/1] min-h-32"
        />
        <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-end sm:justify-between md:p-6">
          <div className="min-w-0 space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight text-balance">{course.name}</h1>
              <CourseStatusBadge status={course.status} />
            </div>
            <p className="text-sm text-muted-foreground">
              {course.category} · {ACCESS_MODEL_SHORT[course.accessModel]} access · Updated{" "}
              {formatDateTime(course.updatedAt)}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            {getCourseStatusActions(course.status).map((a) => (
              <Button
                key={a.target}
                variant={a.target === "published" ? "default" : "outline"}
                className={a.target === "archived" ? "text-destructive hover:text-destructive" : undefined}
                onClick={() => statusDialog.ask(course, a.target)}
              >
                {a.label}
              </Button>
            ))}
            <Button
              variant="outline"
              nativeButton={false}
              render={<Link href={`/admin/courses/${course.id}/resources`} />}
            >
              <FileText />
              Manage resources
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Enrolled students" value={formatNumber(course.enrolledCount)} icon={Users} />
        <StatCard label="Resources" value={formatNumber(course.resourceCount)} icon={FileText} />
        <StatCard label="Price" value={formatPrice(course.price, course.currency)} icon={Tag} />
        <StatCard label="Access duration" value={formatAccessDuration(course.accessDurationDays)} icon={CalendarClock} />
      </div>

      <Tabs defaultValue="details">
        <TabsList variant="line">
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="resources">
            Resources
            <Badge variant="secondary" className="ml-1 tabular-nums">
              {course.resourceCount}
            </Badge>
          </TabsTrigger>
        </TabsList>
        <TabsContent value="details" className="pt-4">
          <CourseForm
            key={`${course.id}-${course.updatedAt}`}
            mode="edit"
            defaultValues={courseToFormValues(course)}
            isPending={update.isPending}
            onSubmit={async (input) => {
              try {
                await update.mutateAsync(input);
                notify.success("Course updated", input.name);
                return true;
              } catch (err) {
                notify.error(err, "Couldn't save course");
                return false;
              }
            }}
          />
        </TabsContent>
        <TabsContent value="resources" className="pt-4">
          <ResourcesSummary courseId={course.id} />
        </TabsContent>
      </Tabs>

      <CourseStatusDialog request={statusDialog.request} open={statusDialog.open} onOpenChange={statusDialog.onOpenChange} />
    </div>
  );
}

function ResourcesSummary({ courseId }: { courseId: string }) {
  const query = useCourseResources(courseId);
  const resources = query.data ?? [];
  const manageHref = `/admin/courses/${courseId}/resources`;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Resources</CardTitle>
        <CardDescription>Protected PDFs students can open in the secure viewer.</CardDescription>
        <CardAction>
          <Button variant="outline" size="sm" nativeButton={false} render={<Link href={manageHref} />}>
            Manage all
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <ListSkeleton rows={3} />
        ) : query.error ? (
          <ErrorState compact error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
        ) : resources.length === 0 ? (
          <EmptyState
            compact
            icon={FileText}
            title="No resources yet"
            description="Upload PDFs to give enrolled students something to study."
            action={
              <Button size="sm" nativeButton={false} render={<Link href={manageHref} />}>
                Upload PDF
              </Button>
            }
          />
        ) : (
          <div className="space-y-3">
            {resources.slice(0, RESOURCE_PREVIEW_COUNT).map((r) => (
              <ResourceCard key={r.id} resource={r} action={<ResourceStatusBadge status={r.status} />} />
            ))}
            {resources.length > RESOURCE_PREVIEW_COUNT && (
              <p className="pt-1 text-sm text-muted-foreground">
                Showing {RESOURCE_PREVIEW_COUNT} of {resources.length} resources.{" "}
                <Link href={manageHref} className="font-medium text-primary hover:underline">
                  View all
                </Link>
              </p>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
