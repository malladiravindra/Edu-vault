"use client";

import { useState } from "react";
import { SearchX } from "lucide-react";
import type { StudentCourse, StudentCourseAccess } from "@/types";
import { useCourseCatalog, useCourseCategories } from "@/hooks/use-courses";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { DataTableToolbar } from "@/components/shared/data-table";
import { SearchBar } from "@/components/shared/search-bar";
import { FilterDropdown, type FilterOption } from "@/components/shared/filter-dropdown";
import { CourseCard } from "@/components/shared/course-card";
import { CardGridSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Pagination } from "@/components/shared/pagination";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { RequestAccessDialog } from "./request-access-dialog";

const CATALOG_PAGE_SIZE = 9;

type Filters = { category?: string; access?: StudentCourseAccess };

const ACCESS_OPTIONS: FilterOption<StudentCourseAccess>[] = [
  { value: "none", label: "Available" },
  { value: "active", label: "Active" },
  { value: "pending", label: "Pending" },
  { value: "payment_required", label: "Payment Required" },
  { value: "expired", label: "Expired" },
];

export function CourseCatalogView() {
  const list = useListState<Filters>({}, CATALOG_PAGE_SIZE);
  const query = useCourseCatalog(list.params);
  const categories = useCourseCategories();
  const [requestCourse, setRequestCourse] = useState<StudentCourse | null>(null);
  const [requestOpen, setRequestOpen] = useState(false);

  const categoryOptions: FilterOption[] = (categories.data ?? []).map((c) => ({ value: c, label: c }));
  const courses = query.data?.data ?? [];

  const openRequest = (course: StudentCourse) => {
    setRequestCourse(course);
    setRequestOpen(true);
  };

  let content;
  if (query.isLoading) {
    content = <CardGridSkeleton count={CATALOG_PAGE_SIZE} />;
  } else if (query.error) {
    content = (
      <div className="rounded-xl border bg-card">
        <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
      </div>
    );
  } else if (courses.length === 0) {
    content = (
      <div className="rounded-xl border border-dashed bg-card">
        <EmptyState
          icon={SearchX}
          title="No courses match your filters"
          description="Try a different search term or clear your filters to see the full catalog."
          action={
            list.hasActiveFilters ? (
              <Button variant="outline" size="sm" onClick={list.reset}>
                Clear filters
              </Button>
            ) : undefined
          }
        />
      </div>
    );
  } else {
    content = (
      <div className="space-y-6">
        <div
          className={cn(
            "grid gap-5 transition-opacity sm:grid-cols-2 xl:grid-cols-3",
            query.isFetching && "opacity-60",
          )}
        >
          {courses.map((course) => (
            <CourseCard key={course.id} course={course} onRequestAccess={openRequest} />
          ))}
        </div>
        {query.data && (
          <Pagination
            page={query.data.page}
            totalPages={query.data.totalPages}
            total={query.data.total}
            pageSize={query.data.pageSize}
            onPageChange={list.setPage}
            itemLabel="courses"
          />
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Browse Courses"
        description="Explore the catalog and request access to the courses you'd like to take."
      />

      <DataTableToolbar>
        <SearchBar
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search courses or topics"
          className="sm:w-80"
        />
        <FilterDropdown
          label="Category"
          allLabel="All categories"
          value={list.filters.category}
          onChange={(v) => list.setFilter("category", v)}
          options={categoryOptions}
        />
        <FilterDropdown
          label="Access"
          allLabel="All courses"
          value={list.filters.access}
          onChange={(v) => list.setFilter("access", v)}
          options={ACCESS_OPTIONS}
        />
        {list.hasActiveFilters && (
          <Button variant="ghost" size="sm" onClick={list.reset}>
            Clear filters
          </Button>
        )}
      </DataTableToolbar>

      {content}

      <RequestAccessDialog course={requestCourse} open={requestOpen} onOpenChange={setRequestOpen} />
    </div>
  );
}
