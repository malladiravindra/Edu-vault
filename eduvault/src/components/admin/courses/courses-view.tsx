"use client";

import Link from "next/link";
import { BookOpen, FileText, MoreHorizontal, Pencil, Plus } from "lucide-react";
import type { AccessModel, Course, CourseStatus } from "@/types";
import { ACCESS_MODEL_LABEL, COURSE_STATUS, toOptions } from "@/lib/constants";
import { formatAccessDuration, formatDate, formatNumber, formatPrice } from "@/lib/format";
import { useCourses } from "@/hooks/use-courses";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, DataTableToolbar, type DataTableColumn } from "@/components/shared/data-table";
import { SearchBar } from "@/components/shared/search-bar";
import { FilterDropdown } from "@/components/shared/filter-dropdown";
import { CourseStatusBadge } from "@/components/shared/status-badge";
import { CourseCover } from "@/components/shared/course-cover";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { CourseStatusDialog, getCourseStatusActions, useCourseStatusDialog } from "./course-status-dialog";
import { ACCESS_MODEL_SHORT } from "./course-schema";

type Filters = { status?: CourseStatus; accessModel?: AccessModel };


export function CoursesView() {
  const list = useListState<Filters>({});
  const query = useCourses(list.params);
  const statusDialog = useCourseStatusDialog();

  const columns: DataTableColumn<Course>[] = [
    {
      id: "course",
      header: "Course",
      className: "min-w-64",
      cell: (c) => (
        <div className="flex items-center gap-3">
          <CourseCover
            courseId={c.id}
            name={c.name}
            category={c.category}
            imageUrl={c.imageUrl}
            className="hidden h-10 w-14 shrink-0 rounded-md sm:block [&_span]:hidden"
          />
          <div className="min-w-0">
            <Link
              href={`/admin/courses/${c.id}`}
              className="block truncate font-medium hover:underline focus-visible:underline"
            >
              {c.name}
            </Link>
            <p className="truncate text-xs text-muted-foreground">{c.category}</p>
          </div>
        </div>
      ),
    },
    {
      id: "price",
      header: "Price",
      cell: (c) => <span className="tabular-nums">{formatPrice(c.price, c.currency)}</span>,
    },
    {
      id: "access",
      header: "Access model",
      hideBelow: "md",
      cell: (c) => <span className="text-muted-foreground">{ACCESS_MODEL_SHORT[c.accessModel]}</span>,
    },
    {
      id: "duration",
      header: "Duration",
      hideBelow: "lg",
      cell: (c) => <span className="text-muted-foreground">{formatAccessDuration(c.accessDurationDays)}</span>,
    },
    {
      id: "resources",
      header: "Resources",
      align: "right",
      hideBelow: "lg",
      cell: (c) => <span className="tabular-nums">{formatNumber(c.resourceCount)}</span>,
    },
    {
      id: "enrolled",
      header: "Enrolled",
      align: "right",
      hideBelow: "sm",
      cell: (c) => <span className="tabular-nums">{formatNumber(c.enrolledCount)}</span>,
    },
    { id: "status", header: "Status", cell: (c) => <CourseStatusBadge status={c.status} /> },
    {
      id: "updated",
      header: "Updated",
      hideBelow: "xl",
      cell: (c) => <span className="text-muted-foreground tabular-nums">{formatDate(c.updatedAt)}</span>,
    },
    {
      id: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (c) => (
        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="ghost" size="icon-sm" aria-label={`Actions for ${c.name}`} />}
          >
            <MoreHorizontal />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem render={<Link href={`/admin/courses/${c.id}`} />}>
              <Pencil />
              View / edit
            </DropdownMenuItem>
            <DropdownMenuItem render={<Link href={`/admin/courses/${c.id}/resources`} />}>
              <FileText />
              Manage resources
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            {getCourseStatusActions(c.status).map((a) => (
              <DropdownMenuItem
                key={a.target}
                variant={a.target === "archived" ? "destructive" : "default"}
                onClick={() => statusDialog.ask(c, a.target)}
              >
                {a.label}
              </DropdownMenuItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Courses"
        description="Create courses, set pricing and access rules, and control what appears in the catalog."
        actions={
          <Button nativeButton={false} render={<Link href="/admin/courses/create" />}>
            <Plus />
            Create course
          </Button>
        }
      />

      <DataTableToolbar>
        <SearchBar
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search courses or categories"
          className="sm:w-80"
        />
        <FilterDropdown
          label="Status"
          allLabel="All statuses"
          value={list.filters.status}
          onChange={(v) => list.setFilter("status", v)}
          options={toOptions(COURSE_STATUS)}
        />
        <FilterDropdown
          label="Access model"
          allLabel="All access models"
          value={list.filters.accessModel}
          onChange={(v) => list.setFilter("accessModel", v)}
          options={toOptions(ACCESS_MODEL_LABEL)}
          className="sm:w-56"
        />
        {list.hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={list.reset}>
            Clear filters
          </Button>
        )}
      </DataTableToolbar>

      <DataTable
        columns={columns}
        data={query.data}
        getRowId={(c) => c.id}
        isLoading={query.isLoading}
        isFetching={query.isFetching}
        error={query.error}
        onRetry={() => query.refetch()}
        onPageChange={list.setPage}
        emptyIcon={BookOpen}
        emptyTitle={list.hasActiveFilters ? "No courses match your filters" : "No courses yet"}
        emptyDescription={
          list.hasActiveFilters
            ? "Try a different search or clear the filters."
            : "Create your first course to start adding protected resources."
        }
        emptyAction={
          list.hasActiveFilters ? undefined : (
            <Button nativeButton={false} render={<Link href="/admin/courses/create" />}>
              <Plus />
              Create course
            </Button>
          )
        }
        itemLabel="courses"
        caption="Courses"
      />

      <CourseStatusDialog request={statusDialog.request} open={statusDialog.open} onOpenChange={statusDialog.onOpenChange} />
    </div>
  );
}
