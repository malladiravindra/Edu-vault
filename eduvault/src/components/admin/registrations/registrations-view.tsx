"use client";

import { useState } from "react";
import { ClipboardCheck, Eye, MoreHorizontal } from "lucide-react";
import type { Registration, RegistrationStatus } from "@/types";
import { REGISTRATION_STATUS } from "@/lib/constants";
import { formatDate } from "@/lib/format";
import { useRegistrations } from "@/hooks/use-registrations";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, DataTableToolbar, type DataTableColumn } from "@/components/shared/data-table";
import { SearchBar } from "@/components/shared/search-bar";
import { RegistrationStatusBadge } from "@/components/shared/status-badge";
import { UserCell } from "@/components/shared/user-avatar";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  DECISION_LABEL,
  DECISION_ORDER,
  RegistrationDecisionDialog,
  type RegistrationDecision,
} from "./registration-decision-dialog";
import { RegistrationDrawer } from "./registration-drawer";

type Filters = { status?: RegistrationStatus };
type TabValue = RegistrationStatus | "all";

const TABS: { value: TabValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "pending", label: REGISTRATION_STATUS.pending.label },
  { value: "immediate_access", label: REGISTRATION_STATUS.immediate_access.label },
  { value: "payment_required", label: REGISTRATION_STATUS.payment_required.label },
];

const EMPTY_COPY: Record<TabValue, { title: string; description: string }> = {
  all: { title: "No registrations yet", description: "Course access requests from students will appear here." },
  pending: { title: "No pending registrations", description: "You're all caught up. New requests will show up here." },
  immediate_access: {
    title: "No registrations with immediate access",
    description: "Registrations you grant immediate access to will appear here.",
  },
  payment_required: {
    title: "No registrations awaiting payment",
    description: "Registrations that require payment will appear here.",
  },
};

export function RegistrationsView() {
  const list = useListState<Filters>({});
  const query = useRegistrations(list.params);

  const [selected, setSelected] = useState<Registration | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [decision, setDecision] = useState<RegistrationDecision | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const tab: TabValue = list.filters.status ?? "all";

  const openDetails = (reg: Registration) => {
    setSelected(reg);
    setDrawerOpen(true);
  };

  const decide = (registration: Registration, status: RegistrationStatus) => {
    setDecision({ registration, status });
    setDialogOpen(true);
  };

  const columns: DataTableColumn<Registration>[] = [
    {
      id: "student",
      header: "Student",
      cell: (r) => <UserCell name={r.studentName} />,
      className: "min-w-44",
    },
    {
      id: "email",
      header: "Email",
      cell: (r) => <span className="text-muted-foreground">{r.studentEmail}</span>,
      hideBelow: "md",
    },
    {
      id: "course",
      header: "Requested Course",
      cell: (r) => <span className="line-clamp-2 font-medium">{r.courseName}</span>,
      className: "min-w-48 max-w-72 whitespace-normal",
    },
    {
      id: "date",
      header: "Registration Date",
      cell: (r) => <span className="text-muted-foreground tabular-nums">{formatDate(r.createdAt)}</span>,
      hideBelow: "lg",
    },
    { id: "status", header: "Status", cell: (r) => <RegistrationStatusBadge status={r.status} />, hideBelow: "sm" },
    {
      id: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      className: "w-12",
      cell: (r) => (
        <div onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon-sm" aria-label={`Actions for ${r.studentName}`} />}
            >
              <MoreHorizontal />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuItem onClick={() => openDetails(r)}>
                <Eye />
                View details
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              {DECISION_ORDER.filter((s) => s !== r.status).map((s) => (
                <DropdownMenuItem key={s} onClick={() => decide(r, s)}>
                  {DECISION_LABEL[s]}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      ),
    },
  ];

  const empty = list.search
    ? { title: "No registrations found", description: "No registrations match your search." }
    : EMPTY_COPY[tab];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Registrations"
        description="Review course access requests and decide whether students get immediate access or need to pay first."
      />

      <div className="space-y-4">
        <div className="overflow-x-auto border-b">
          <Tabs
            value={tab}
            onValueChange={(v) => {
              const next = String(v) as TabValue;
              list.setFilter("status", next === "all" ? undefined : next);
            }}
          >
            <TabsList variant="line" aria-label="Filter by status">
              {TABS.map((t) => (
                <TabsTrigger key={t.value} value={t.value} className="px-3">
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        </div>

        <DataTableToolbar>
          <SearchBar
            value={list.search}
            onChange={list.setSearch}
            placeholder="Search student, email or course"
            className="sm:w-80"
          />
          {list.search && (
            <Button variant="ghost" size="sm" onClick={() => list.setSearch("")}>
              Clear search
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
          onRowClick={openDetails}
          onPageChange={list.setPage}
          emptyIcon={ClipboardCheck}
          emptyTitle={empty.title}
          emptyDescription={empty.description}
          itemLabel="registrations"
          caption="Course registrations"
        />
      </div>

      <RegistrationDrawer
        registration={selected}
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        onDecide={decide}
      />

      <RegistrationDecisionDialog
        decision={decision}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onDone={(updated) => {
          if (selected?.id === updated.id) setSelected(updated);
        }}
      />
    </div>
  );
}
