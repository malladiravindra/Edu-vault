"use client";

import { useMemo, useState } from "react";
import { CalendarPlus, KeyRound, MoreHorizontal, PauseCircle, PlayCircle } from "lucide-react";
import type { AccessRecord, AccessStatus } from "@/types";
import { ACCESS_STATUS } from "@/lib/constants";
import { daysUntil, formatDate } from "@/lib/format";
import { notify } from "@/lib/toast";
import { useAccessRecords, useUpdateAccessStatus } from "@/hooks/use-access";
import { useCourses } from "@/hooks/use-courses";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, DataTableToolbar, type DataTableColumn } from "@/components/shared/data-table";
import { SearchBar } from "@/components/shared/search-bar";
import { FilterDropdown } from "@/components/shared/filter-dropdown";
import { ConfirmationDialog } from "@/components/shared/confirmation-dialog";
import { AccessStatusBadge, PaymentStatusBadge } from "@/components/shared/status-badge";
import { UserCell } from "@/components/shared/user-avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AccessSummary, ACCESS_STATUS_ORDER } from "./access-summary";
import { ExtendAccessModal } from "./extend-access-modal";

type Filters = { status?: AccessStatus; courseId?: string };

const EXPIRY_WARNING_DAYS = 14;

const STATUS_OPTIONS = ACCESS_STATUS_ORDER.map((value) => ({ value, label: ACCESS_STATUS[value].label }));

function ExpiryCell({ record }: { record: AccessRecord }) {
  if (!record.expiresAt) {
    return <span className="text-muted-foreground">{record.status === "active" ? "Lifetime" : "—"}</span>;
  }
  const days = daysUntil(record.expiresAt);
  const expiringSoon = record.status === "active" && days !== null && days >= 0 && days <= EXPIRY_WARNING_DAYS;
  return (
    <div className="tabular-nums">
      <span className={expiringSoon ? "font-medium" : "text-muted-foreground"}>{formatDate(record.expiresAt)}</span>
      {expiringSoon && (
        <span className="block text-xs font-medium text-warning">
          {days === 0 ? "Expires today" : `in ${days} ${days === 1 ? "day" : "days"}`}
        </span>
      )}
    </div>
  );
}

type PendingAction = { record: AccessRecord; status: "active" | "suspended" };

export function AccessView() {
  const list = useListState<Filters>({});
  const query = useAccessRecords(list.params);
  const coursesQuery = useCourses({ pageSize: 100 });
  const updateStatus = useUpdateAccessStatus();

  const [extending, setExtending] = useState<AccessRecord | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction | null>(null);

  const courseOptions = useMemo(
    () => (coursesQuery.data?.data ?? []).map((c) => ({ value: c.id, label: c.name })),
    [coursesQuery.data],
  );

  const confirmStatusChange = () => {
    if (!pendingAction) return;
    const { record, status } = pendingAction;
    updateStatus.mutate(
      { id: record.id, status },
      {
        onSuccess: () => {
          notify.success(
            status === "suspended" ? "Access suspended" : "Access reactivated",
            `${record.studentName} · ${record.courseName}`,
          );
          setPendingAction(null);
        },
        onError: (err) =>
          notify.error(err, status === "suspended" ? "Couldn't suspend access" : "Couldn't reactivate access"),
      },
    );
  };

  const columns: DataTableColumn<AccessRecord>[] = [
    {
      id: "student",
      header: "Student",
      cell: (r) => <UserCell name={r.studentName} email={r.studentEmail} />,
      className: "min-w-52",
    },
    {
      id: "course",
      header: "Course",
      cell: (r) => <span className="line-clamp-2 font-medium">{r.courseName}</span>,
      className: "min-w-44 max-w-72 whitespace-normal",
    },
    { id: "status", header: "Access", cell: (r) => <AccessStatusBadge status={r.status} /> },
    {
      id: "granted",
      header: "Granted",
      cell: (r) => (
        <span className="text-muted-foreground tabular-nums">{r.grantedAt ? formatDate(r.grantedAt) : "—"}</span>
      ),
      hideBelow: "lg",
    },
    { id: "expires", header: "Expires", cell: (r) => <ExpiryCell record={r} />, hideBelow: "md" },
    { id: "payment", header: "Payment", cell: (r) => <PaymentStatusBadge status={r.paymentStatus} />, hideBelow: "sm" },
    {
      id: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      className: "w-12",
      cell: (r) => {
        // Lifetime access can't be "extended"; expired access is restored by extending it.
        const canExtend = r.status === "expired" || (r.status === "active" && Boolean(r.expiresAt));
        const canSuspend = r.status !== "suspended" && r.status !== "expired";
        return (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${r.studentName}, ${r.courseName}`} />
              }
            >
              <MoreHorizontal />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              {canExtend && (
                <DropdownMenuItem onClick={() => setExtending(r)}>
                  <CalendarPlus />
                  Extend access
                </DropdownMenuItem>
              )}
              {r.status === "suspended" && (
                <DropdownMenuItem onClick={() => setPendingAction({ record: r, status: "active" })}>
                  <PlayCircle />
                  Reactivate
                </DropdownMenuItem>
              )}
              {canSuspend && (
                <>
                  {canExtend && <DropdownMenuSeparator />}
                  <DropdownMenuItem
                    variant="destructive"
                    onClick={() => setPendingAction({ record: r, status: "suspended" })}
                  >
                    <PauseCircle />
                    Suspend access
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
    },
  ];

  const suspending = pendingAction?.status === "suspended";

  return (
    <div className="space-y-6">
      <PageHeader
        title="Access Management"
        description="Review who can open each course, extend expiring access, and suspend or restore enrollments."
      />

      <AccessSummary selected={list.filters.status} onSelect={(s) => list.setFilter("status", s)} />

      <DataTableToolbar>
        <SearchBar
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search student or course"
          className="sm:w-80"
        />
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
        getRowId={(r) => r.id}
        isLoading={query.isLoading}
        isFetching={query.isFetching}
        error={query.error}
        onRetry={() => query.refetch()}
        onPageChange={list.setPage}
        emptyIcon={KeyRound}
        emptyTitle="No access records found"
        emptyDescription={
          list.hasActiveFilters
            ? "No access records match your current filters."
            : "Access records appear once students enroll in a course."
        }
        itemLabel="records"
        caption="Course access records"
      />

      <ExtendAccessModal record={extending} onOpenChange={(open) => !open && setExtending(null)} />

      <ConfirmationDialog
        open={pendingAction !== null}
        onOpenChange={(open) => !open && setPendingAction(null)}
        title={suspending ? "Suspend access?" : "Reactivate access?"}
        description={
          pendingAction
            ? suspending
              ? `${pendingAction.record.studentName} will immediately lose access to "${pendingAction.record.courseName}" until it is reactivated.`
              : `${pendingAction.record.studentName} will regain access to "${pendingAction.record.courseName}".`
            : ""
        }
        confirmLabel={suspending ? "Suspend access" : "Reactivate"}
        destructive={suspending}
        loading={updateStatus.isPending}
        onConfirm={confirmStatusChange}
      />
    </div>
  );
}
