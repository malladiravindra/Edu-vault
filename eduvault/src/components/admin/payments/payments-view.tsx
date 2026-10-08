"use client";

import { useState } from "react";
import { ChevronRight, CreditCard, Download } from "lucide-react";
import type { Payment, PaymentStatus } from "@/types";
import { PAYMENT_STATUS } from "@/lib/constants";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { notify } from "@/lib/toast";
import { usePayments } from "@/hooks/use-payments";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, DataTableToolbar, type DataTableColumn } from "@/components/shared/data-table";
import { SearchBar } from "@/components/shared/search-bar";
import { FilterDropdown } from "@/components/shared/filter-dropdown";
import { DateRangeFilter, type DateRange } from "@/components/shared/date-range-filter";
import { PaymentStatusBadge } from "@/components/shared/status-badge";
import { UserCell } from "@/components/shared/user-avatar";
import { Button } from "@/components/ui/button";
import { PaymentsSummary } from "./payments-summary";
import { PaymentDetailsDrawer } from "./payment-details-drawer";
import { CopyTransactionButton } from "./copy-transaction-button";

type Filters = { status?: PaymentStatus };

const STATUS_VALUES: PaymentStatus[] = ["successful", "pending", "failed", "refunded"];
const STATUS_OPTIONS = STATUS_VALUES.map((value) => ({ value, label: PAYMENT_STATUS[value].label }));

function buildColumns(onView: (payment: Payment) => void): DataTableColumn<Payment>[] {
  return [
  {
    id: "student",
    header: "Student",
    cell: (p) => <UserCell name={p.studentName} email={p.studentEmail} />,
    className: "min-w-52",
  },
  {
    id: "course",
    header: "Course",
    cell: (p) => <span className="line-clamp-2">{p.courseName}</span>,
    className: "min-w-44 max-w-72 whitespace-normal",
    hideBelow: "md",
  },
  {
    id: "amount",
    header: "Amount",
    align: "right",
    cell: (p) => <span className="font-medium tabular-nums">{formatCurrency(p.amount, p.currency)}</span>,
  },
  { id: "status", header: "Status", cell: (p) => <PaymentStatusBadge status={p.status} /> },
  {
    id: "transaction",
    header: "Transaction ID",
    hideBelow: "lg",
    cell: (p) => (
      <span className="inline-flex items-center gap-1">
        <span className="font-mono text-xs text-muted-foreground">{p.transactionId}</span>
        <CopyTransactionButton value={p.transactionId} />
      </span>
    ),
  },
  {
    id: "date",
    header: "Date",
    hideBelow: "sm",
    cell: (p) => <span className="text-muted-foreground tabular-nums">{formatDateTime(p.createdAt)}</span>,
  },
  {
    // Keyboard-accessible alternative to clicking the row.
    id: "view",
    header: <span className="sr-only">Details</span>,
    align: "right",
    className: "w-12",
    cell: (p) => (
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={`View payment details for ${p.studentName}`}
        onClick={(e) => {
          e.stopPropagation();
          onView(p);
        }}
      >
        <ChevronRight />
      </Button>
    ),
  },
  ];
}

export function PaymentsView() {
  const list = useListState<Filters>({});
  const [range, setRange] = useState<DateRange>({});
  const [selected, setSelected] = useState<Payment | null>(null);
  const query = usePayments({ ...list.params, ...range });
  const columns = buildColumns(setSelected);

  const hasFilters = list.hasActiveFilters || Boolean(range.from || range.to);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Payments"
        description="Track course payments, confirm transactions and review payment history."
        actions={
          <Button variant="outline" onClick={() => notify.info("Export started", "We'll prepare a CSV of your payments.")}>
            <Download aria-hidden />
            Export
          </Button>
        }
      />

      <PaymentsSummary />

      <DataTableToolbar>
        <SearchBar
          value={list.search}
          onChange={list.setSearch}
          placeholder="Search student, course or transaction ID"
          className="sm:w-80"
        />
        <FilterDropdown
          label="Status"
          allLabel="All statuses"
          value={list.filters.status}
          onChange={(v) => list.setFilter("status", v)}
          options={STATUS_OPTIONS}
        />
        <DateRangeFilter
          value={range}
          onChange={(r) => {
            setRange(r);
            list.setPage(1);
          }}
        />
        {hasFilters && (
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
        getRowId={(p) => p.id}
        isLoading={query.isLoading}
        isFetching={query.isFetching}
        error={query.error}
        onRetry={() => query.refetch()}
        onRowClick={setSelected}
        onPageChange={list.setPage}
        emptyIcon={CreditCard}
        emptyTitle="No payments found"
        emptyDescription={hasFilters ? "No payments match your current filters." : "Payments appear here once students check out."}
        itemLabel="payments"
        caption="Payments. Select a row to view details."
      />

      <PaymentDetailsDrawer payment={selected} onOpenChange={(open) => !open && setSelected(null)} />
    </div>
  );
}
