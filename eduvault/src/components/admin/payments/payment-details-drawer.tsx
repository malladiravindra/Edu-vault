"use client";

import type { ReactNode } from "react";
import { Info } from "lucide-react";
import type { Payment } from "@/types";
import { formatCurrency, formatDateTime } from "@/lib/format";
import { SideDrawer } from "@/components/shared/side-drawer";
import { PaymentStatusBadge } from "@/components/shared/status-badge";
import { UserCell } from "@/components/shared/user-avatar";
import { CopyTransactionButton } from "./copy-transaction-button";

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2.5 text-sm">
      <dt className="shrink-0 text-muted-foreground">{label}</dt>
      <dd className="min-w-0 text-right font-medium break-words">{children}</dd>
    </div>
  );
}

interface PaymentDetailsDrawerProps {
  payment: Payment | null;
  onOpenChange: (open: boolean) => void;
}

export function PaymentDetailsDrawer({ payment, onOpenChange }: PaymentDetailsDrawerProps) {
  return (
    <SideDrawer
      open={payment !== null}
      onOpenChange={onOpenChange}
      title="Payment details"
      description={payment ? formatDateTime(payment.createdAt) : undefined}
    >
      {payment && (
        <div className="space-y-6">
          <div className="rounded-xl border bg-muted/30 p-4">
            <p className="text-sm text-muted-foreground">Amount</p>
            <div className="mt-1 flex items-center justify-between gap-3">
              <p className="text-2xl font-semibold tracking-tight tabular-nums">
                {formatCurrency(payment.amount, payment.currency)}
              </p>
              <PaymentStatusBadge status={payment.status} />
            </div>
          </div>

          <section aria-labelledby="payment-student-heading" className="space-y-2">
            <h3 id="payment-student-heading" className="text-sm font-medium">
              Student
            </h3>
            <UserCell name={payment.studentName} email={payment.studentEmail} />
          </section>

          <section aria-labelledby="payment-info-heading">
            <h3 id="payment-info-heading" className="text-sm font-medium">
              Transaction
            </h3>
            <dl className="divide-y">
              <Row label="Course">{payment.courseName}</Row>
              <Row label="Method">{payment.method}</Row>
              <Row label="Currency">{payment.currency.toUpperCase()}</Row>
              <Row label="Date">{formatDateTime(payment.createdAt)}</Row>
              <Row label="Transaction ID">
                <span className="inline-flex items-center gap-1">
                  <span className="font-mono text-xs">{payment.transactionId}</span>
                  <CopyTransactionButton value={payment.transactionId} />
                </span>
              </Row>
              <Row label="Payment ID">
                <span className="font-mono text-xs">{payment.id}</span>
              </Row>
              <Row label="Student ID">
                <span className="font-mono text-xs">{payment.studentId}</span>
              </Row>
              <Row label="Course ID">
                <span className="font-mono text-xs">{payment.courseId}</span>
              </Row>
            </dl>
          </section>

          <p className="flex gap-2 rounded-lg bg-muted/50 p-3 text-xs text-muted-foreground">
            <Info className="mt-px size-3.5 shrink-0" aria-hidden />
            Refunds and disputes are processed through the payment provider dashboard.
          </p>
        </div>
      )}
    </SideDrawer>
  );
}
