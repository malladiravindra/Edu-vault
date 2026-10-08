"use client";

import Link from "next/link";
import { AlertCircle, Receipt } from "lucide-react";
import type { Payment } from "@/types";
import { formatAccessDuration, formatCurrency, formatDateTime, formatPrice } from "@/lib/format";
import { useMyPayments } from "@/hooks/use-payments";
import { useMyCourses } from "@/hooks/use-courses";
import { useListState } from "@/hooks/use-list-state";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, type DataTableColumn } from "@/components/shared/data-table";
import { PaymentStatusBadge } from "@/components/shared/status-badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { CourseThumbnail } from "../shared/course-thumbnail";

const columns: DataTableColumn<Payment>[] = [
  {
    id: "course",
    header: "Course",
    cell: (p) => <span className="font-medium">{p.courseName}</span>,
    className: "min-w-48 whitespace-normal",
  },
  {
    id: "amount",
    header: "Amount",
    cell: (p) => <span className="tabular-nums">{formatCurrency(p.amount, p.currency)}</span>,
    align: "right",
  },
  { id: "status", header: "Status", cell: (p) => <PaymentStatusBadge status={p.status} /> },
  {
    id: "transaction",
    header: "Transaction ID",
    cell: (p) => <span className="font-mono text-xs text-muted-foreground">{p.transactionId}</span>,
    hideBelow: "md",
  },
  { id: "method", header: "Method", cell: (p) => <span className="text-muted-foreground">{p.method}</span>, hideBelow: "lg" },
  {
    id: "date",
    header: "Date",
    cell: (p) => <span className="text-muted-foreground tabular-nums">{formatDateTime(p.createdAt)}</span>,
    hideBelow: "sm",
  },
];

export function PaymentsView() {
  const list = useListState({});
  const payments = useMyPayments(list.params);

  return (
    <div className="space-y-6">
      <PageHeader title="Payments" description="Complete outstanding payments and review your payment history." />

      <ActionRequired />

      <section className="space-y-3" aria-labelledby="payment-history-heading">
        <h2 id="payment-history-heading" className="text-base font-semibold">
          Payment history
        </h2>
        <DataTable
          columns={columns}
          data={payments.data}
          getRowId={(p) => p.id}
          isLoading={payments.isLoading}
          isFetching={payments.isFetching}
          error={payments.error}
          onRetry={() => payments.refetch()}
          onPageChange={list.setPage}
          emptyIcon={Receipt}
          emptyTitle="No payments yet"
          emptyDescription="Payments for paid courses will appear here once completed."
          itemLabel="payments"
          caption="Payment history"
        />
      </section>
    </div>
  );
}

/** Highlights approved courses still awaiting payment. Silent while loading or on error. */
function ActionRequired() {
  const courses = useMyCourses();
  const due = (courses.data ?? []).filter((c) => c.access === "payment_required");
  if (due.length === 0) return null;

  return (
    <Card className="border-primary/30 bg-primary/[0.03]">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <AlertCircle className="size-4.5 text-primary" aria-hidden />
          <h2>Action required</h2>
        </CardTitle>
        <CardDescription>
          {due.length === 1
            ? "Your request for this course was approved. Complete payment to unlock it."
            : `Your requests for ${due.length} courses were approved. Complete payment to unlock them.`}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="divide-y rounded-lg border bg-card">
          {due.map((course) => (
            <li key={course.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center">
              <div className="flex min-w-0 flex-1 items-center gap-3">
                <CourseThumbnail course={course} className="h-12 w-16" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{course.name}</p>
                  <p className="text-xs text-muted-foreground">
                    <span className="tabular-nums">{formatPrice(course.price, course.currency)}</span> ·{" "}
                    {formatAccessDuration(course.accessDurationDays)}
                  </p>
                </div>
              </div>
              <Button
                size="sm"
                nativeButton={false}
                render={<Link href={`/student/payments/checkout?course=${course.id}`} />}
              >
                Proceed to Payment
              </Button>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
