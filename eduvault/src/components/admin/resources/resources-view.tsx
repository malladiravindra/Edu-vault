"use client";

import Link from "next/link";
import { ChevronRight, FileText, FolderOpen } from "lucide-react";
import { formatNumber } from "@/lib/format";
import { useCourses } from "@/hooks/use-courses";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { SearchBar } from "@/components/shared/search-bar";
import { DataTableToolbar } from "@/components/shared/data-table";
import { CourseCover } from "@/components/shared/course-cover";
import { CourseStatusBadge } from "@/components/shared/status-badge";
import { CardGridSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";

export function ResourcesView() {
  const list = useListState({}, 100);
  const query = useCourses(list.params);
  const courses = query.data?.data ?? [];

  let content;
  if (query.isLoading) {
    content = <CardGridSkeleton count={6} />;
  } else if (query.error) {
    content = (
      <div className="rounded-xl border bg-card">
        <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
      </div>
    );
  } else if (courses.length === 0) {
    content = (
      <div className="rounded-xl border bg-card">
        <EmptyState
          icon={FolderOpen}
          title={list.search ? "No courses match your search" : "No courses yet"}
          description={
            list.search ? "Try a different course name or category." : "Create a course before uploading resources."
          }
          action={
            list.search ? (
              <Button variant="outline" size="sm" onClick={list.reset}>
                Clear search
              </Button>
            ) : (
              <Button nativeButton={false} render={<Link href="/admin/courses/create" />}>
                Create course
              </Button>
            )
          }
        />
      </div>
    );
  } else {
    content = (
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-label="Courses">
        {courses.map((c) => (
          <li key={c.id}>
            <Link
              href={`/admin/courses/${c.id}/resources`}
              className="group flex h-full items-center gap-4 rounded-xl border bg-card p-4 transition-colors outline-none hover:bg-muted/40 focus-visible:ring-3 focus-visible:ring-ring/50"
            >
              <CourseCover
                courseId={c.id}
                name={c.name}
                category={c.category}
                imageUrl={c.imageUrl}
                className="h-14 w-20 shrink-0 rounded-lg [&_span]:hidden"
              />
              <div className="min-w-0 flex-1 space-y-1">
                <p className="truncate text-sm font-medium">{c.name}</p>
                <p className="truncate text-xs text-muted-foreground">{c.category}</p>
                <div className="flex flex-wrap items-center gap-2 pt-0.5">
                  <CourseStatusBadge status={c.status} />
                  <span className="inline-flex items-center gap-1 text-xs text-muted-foreground tabular-nums">
                    <FileText className="size-3.5" aria-hidden />
                    {formatNumber(c.resourceCount)} {c.resourceCount === 1 ? "resource" : "resources"}
                  </span>
                </div>
              </div>
              <ChevronRight
                className="size-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                aria-hidden
              />
            </Link>
          </li>
        ))}
      </ul>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Resources" description="Manage protected PDF resources for each course." />

      <DataTableToolbar>
        <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search courses" className="sm:w-80" />
        {query.data && !query.isLoading && (
          <p className="text-sm text-muted-foreground sm:ml-auto">
            {formatNumber(query.data.total)} {query.data.total === 1 ? "course" : "courses"}
          </p>
        )}
      </DataTableToolbar>

      <div className={query.isFetching && !query.isLoading ? "opacity-60 transition-opacity" : "transition-opacity"}>
        {content}
      </div>
    </div>
  );
}
