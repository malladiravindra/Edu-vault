"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Ban, Eye, MoreHorizontal, RotateCcw, Users } from "lucide-react";
import type { ID, Student, StudentStatus } from "@/types";
import { STUDENT_STATUS, toOptions } from "@/lib/constants";
import { formatDate, formatNumber } from "@/lib/format";
import { useStudents } from "@/hooks/use-students";
import { useCourses } from "@/hooks/use-courses";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, DataTableToolbar, type DataTableColumn } from "@/components/shared/data-table";
import { SearchBar } from "@/components/shared/search-bar";
import { FilterDropdown } from "@/components/shared/filter-dropdown";
import { StudentStatusBadge } from "@/components/shared/status-badge";
import { UserCell } from "@/components/shared/user-avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { StudentStatusDialog } from "./student-status-dialog";

type Filters = { status?: StudentStatus; courseId?: ID };

const STATUS_OPTIONS = toOptions(STUDENT_STATUS);

export function StudentsView() {
  const router = useRouter();
  const list = useListState<Filters>({});
  const query = useStudents(list.params);
  const courses = useCourses({ pageSize: 100 });

  const [target, setTarget] = useState<Student | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const courseOptions = useMemo(
    () => (courses.data?.data ?? []).map((c) => ({ value: c.id, label: c.name })),
    [courses.data],
  );

  const changeStatus = (student: Student) => {
    setTarget(student);
    setDialogOpen(true);
  };

  const columns: DataTableColumn<Student>[] = [
    {
      id: "name",
      header: "Name",
      cell: (s) => <UserCell name={s.name} src={s.avatarUrl} />,
      className: "min-w-44",
    },
    {
      id: "email",
      header: "Email",
      cell: (s) => <span className="text-muted-foreground">{s.email}</span>,
      hideBelow: "md",
    },
    { id: "status", header: "Status", cell: (s) => <StudentStatusBadge status={s.status} /> },
    {
      id: "courses",
      header: "Courses",
      align: "right",
      cell: (s) => <span className="tabular-nums">{formatNumber(s.enrolledCourseIds.length)}</span>,
      hideBelow: "sm",
    },
    {
      id: "access",
      header: "Active Access",
      align: "right",
      cell: (s) => <span className="tabular-nums">{formatNumber(s.activeAccessCount)}</span>,
      hideBelow: "lg",
    },
    {
      id: "joined",
      header: "Joined Date",
      cell: (s) => <span className="text-muted-foreground tabular-nums">{formatDate(s.createdAt)}</span>,
      hideBelow: "lg",
    },
    {
      id: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      className: "w-12",
      cell: (s) => (
        <div onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          <DropdownMenu>
            <DropdownMenuTrigger render={<Button variant="ghost" size="icon-sm" aria-label={`Actions for ${s.name}`} />}>
              <MoreHorizontal />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuItem render={<Link href={`/admin/students/${s.id}`} />}>
                <Eye />
                View
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {s.status === "suspended" ? (
                <DropdownMenuItem onClick={() => changeStatus(s)}>
                  <RotateCcw />
                  Reinstate
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem variant="destructive" onClick={() => changeStatus(s)}>
                  <Ban />
                  Suspend
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title="Students" description="Manage student accounts, course access and account status." />

      <DataTableToolbar>
        <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search name or email" className="sm:w-80" />
        <FilterDropdown
          label="Status"
          allLabel="All statuses"
          value={list.filters.status}
          onChange={(v) => list.setFilter("status", v)}
          options={STATUS_OPTIONS}
        />
        <FilterDropdown
          label="Course"
          allLabel="All courses"
          value={list.filters.courseId}
          onChange={(v) => list.setFilter("courseId", v)}
          options={courseOptions}
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
        getRowId={(s) => s.id}
        isLoading={query.isLoading}
        isFetching={query.isFetching}
        error={query.error}
        onRetry={() => query.refetch()}
        onRowClick={(s) => router.push(`/admin/students/${s.id}`)}
        onPageChange={list.setPage}
        emptyIcon={Users}
        emptyTitle={list.hasActiveFilters ? "No students found" : "No students yet"}
        emptyDescription={
          list.hasActiveFilters ? "No students match your current filters." : "Students appear here once they sign up."
        }
        itemLabel="students"
        caption="Students"
      />

      <StudentStatusDialog student={target} open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
