"use client";

import { useState } from "react";
import { ScrollText } from "lucide-react";
import type { AuditLog, AuditModule, AuditStatus } from "@/types";
import { AUDIT_MODULE_LABEL, AUDIT_STATUS, toOptions } from "@/lib/constants";
import { formatDateTime } from "@/lib/format";
import { useAuditLogs } from "@/hooks/use-audit-logs";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, DataTableToolbar, type DataTableColumn } from "@/components/shared/data-table";
import { SearchBar } from "@/components/shared/search-bar";
import { FilterDropdown } from "@/components/shared/filter-dropdown";
import { DateRangeFilter, type DateRange } from "@/components/shared/date-range-filter";
import { AuditStatusBadge } from "@/components/shared/status-badge";
import { UserCell } from "@/components/shared/user-avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type Filters = { module?: AuditModule; status?: AuditStatus };

const columns: DataTableColumn<AuditLog>[] = [
  {
    id: "user",
    header: "User",
    cell: (log) => <UserCell name={log.userName} email={log.userEmail} />,
    className: "min-w-52",
  },
  { id: "action", header: "Action", cell: (log) => <span className="font-medium">{log.action}</span> },
  {
    id: "module",
    header: "Module",
    cell: (log) => <Badge variant="outline">{AUDIT_MODULE_LABEL[log.module]}</Badge>,
    hideBelow: "md",
  },
  {
    id: "description",
    header: "Description",
    cell: (log) => <span className="line-clamp-2 text-muted-foreground">{log.description}</span>,
    hideBelow: "lg",
    className: "max-w-80 whitespace-normal",
  },
  {
    id: "date",
    header: "Date",
    cell: (log) => <span className="text-muted-foreground tabular-nums">{formatDateTime(log.createdAt)}</span>,
    hideBelow: "sm",
  },
  { id: "status", header: "Status", cell: (log) => <AuditStatusBadge status={log.status} /> },
];

export function AuditLogsView() {
  const list = useListState<Filters>({});
  const [range, setRange] = useState<DateRange>({});
  const query = useAuditLogs({ ...list.params, ...range });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Logs"
        description="A tamper-evident record of administrative and security events across the platform."
      />

      <DataTableToolbar>
        <SearchBar value={list.search} onChange={list.setSearch} placeholder="Search user, action or description" className="sm:w-80" />
        <FilterDropdown
          label="Module"
          allLabel="All modules"
          value={list.filters.module}
          onChange={(v) => list.setFilter("module", v)}
          options={toOptions(AUDIT_MODULE_LABEL)}
        />
        <FilterDropdown
          label="Status"
          allLabel="All statuses"
          value={list.filters.status}
          onChange={(v) => list.setFilter("status", v)}
          options={toOptions(AUDIT_STATUS)}
        />
        <DateRangeFilter
          value={range}
          onChange={(r) => {
            setRange(r);
            list.setPage(1);
          }}
        />
        {(list.hasActiveFilters || range.from || range.to) && (
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
        getRowId={(log) => log.id}
        isLoading={query.isLoading}
        isFetching={query.isFetching}
        error={query.error}
        onRetry={() => query.refetch()}
        onPageChange={list.setPage}
        emptyIcon={ScrollText}
        emptyTitle="No audit events found"
        emptyDescription="No events match your current filters."
        itemLabel="events"
        caption="Audit log events"
      />
    </div>
  );
}
