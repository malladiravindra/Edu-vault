"use client";

import { useState } from "react";
import Link from "next/link";
import { History, PlayCircle } from "lucide-react";
import type { LearningActivity } from "@/types";
import { formatDateTime, formatDuration, formatRelative } from "@/lib/format";
import { useLearningHistory } from "@/hooks/use-learning";
import { useMyCourses } from "@/hooks/use-courses";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, DataTableToolbar, type DataTableColumn } from "@/components/shared/data-table";
import { SearchBar } from "@/components/shared/search-bar";
import { FilterDropdown } from "@/components/shared/filter-dropdown";
import { DateRangeFilter, type DateRange } from "@/components/shared/date-range-filter";
import { ProgressBar } from "@/components/shared/progress-bar";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { LearningSummary } from "./learning-summary";

type Filters = { courseId?: string };

function continueHref(a: LearningActivity) {
  return `/student/my-courses/${a.courseId}/resources/${a.resourceId}?page=${Math.max(1, a.lastPage)}`;
}

const columns: DataTableColumn<LearningActivity>[] = [
  {
    id: "course",
    header: "Course",
    cell: (a) => <span className="line-clamp-2 text-muted-foreground">{a.courseName}</span>,
    hideBelow: "md",
    className: "max-w-60 whitespace-normal",
  },
  {
    id: "resource",
    header: "Resource",
    cell: (a) => (
      <div className="min-w-0">
        <p className="line-clamp-2 font-medium">{a.resourceName}</p>
        <p className="text-xs text-muted-foreground tabular-nums">
          Page {a.lastPage} of {a.pageCount}
        </p>
      </div>
    ),
    className: "min-w-48 max-w-72 whitespace-normal",
  },
  {
    id: "progress",
    header: "Progress",
    cell: (a) => <ProgressBar value={a.progress} label={`${a.resourceName}: ${Math.round(a.progress)}% complete`} />,
    className: "w-40 min-w-32",
    hideBelow: "sm",
  },
  {
    id: "time",
    header: "Time spent",
    cell: (a) => <span className="tabular-nums">{formatDuration(a.timeSpentMinutes)}</span>,
    hideBelow: "lg",
  },
  {
    id: "lastAccessed",
    header: "Last accessed",
    cell: (a) => (
      <Tooltip>
        <TooltipTrigger
          render={
            <time
              dateTime={a.lastAccessedAt}
              tabIndex={0}
              className="rounded-sm text-muted-foreground tabular-nums focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
            />
          }
        >
          {formatRelative(a.lastAccessedAt)}
        </TooltipTrigger>
        <TooltipContent>{formatDateTime(a.lastAccessedAt)}</TooltipContent>
      </Tooltip>
    ),
    hideBelow: "md",
  },
  {
    id: "action",
    header: <span className="sr-only">Action</span>,
    align: "right",
    cell: (a) => (
      <Button
        variant="outline"
        size="sm"
        nativeButton={false}
        render={<Link href={continueHref(a)} aria-label={`Continue ${a.resourceName}`} />}
      >
        <PlayCircle />
        Continue
      </Button>
    ),
  },
];

export function LearningHistoryView() {
  const list = useListState<Filters>({});
  const [range, setRange] = useState<DateRange>({});
  const query = useLearningHistory({ ...list.params, ...range });
  const courses = useMyCourses();
  const courseOptions = (courses.data ?? []).map((c) => ({ value: c.id, label: c.name }));
  const filtered = list.hasActiveFilters || Boolean(range.from || range.to);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Learning History"
        description="Every resource you've studied, with your progress and time spent"
      />

      <LearningSummary />

      <section aria-labelledby="activity-heading" className="space-y-3">
        <h2 id="activity-heading" className="sr-only">
          Activity
        </h2>
        <DataTableToolbar>
          <SearchBar
            value={list.search}
            onChange={list.setSearch}
            placeholder="Search course or resource"
            className="sm:w-80"
          />
          <FilterDropdown
            label="Course"
            allLabel="All courses"
            value={list.filters.courseId}
            onChange={(v) => list.setFilter("courseId", v)}
            options={courseOptions}
            className="sm:w-56"
          />
          <DateRangeFilter
            value={range}
            onChange={(r) => {
              setRange(r);
              list.setPage(1);
            }}
          />
          {filtered && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                list.reset();
                setRange({});
              }}
            >
              Clear filters
            </Button>
          )}
        </DataTableToolbar>

        <DataTable
          columns={columns}
          data={query.data}
          getRowId={(a) => a.id}
          isLoading={query.isLoading}
          isFetching={query.isFetching}
          error={query.error}
          onRetry={() => query.refetch()}
          onPageChange={list.setPage}
          emptyIcon={History}
          emptyTitle={filtered ? "No matching activity" : "No learning activity yet"}
          emptyDescription={
            filtered
              ? "No resources match your current filters."
              : "Open a resource in one of your courses and your progress will appear here."
          }
          emptyAction={
            filtered ? undefined : (
              <Button size="sm" nativeButton={false} render={<Link href="/student/my-courses" />}>
                Browse my courses
              </Button>
            )
          }
          itemLabel="resources"
          caption="Learning history"
        />
      </section>
    </div>
  );
}
