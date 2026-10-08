"use client";

import type { ReactNode } from "react";
import { BookOpen, CreditCard, KeyRound, LineChart, Activity, Wallet } from "lucide-react";
import type { AccessRecord, ID, LearningActivity, Payment, Student } from "@/types";
import { STUDENT_STATUS } from "@/lib/constants";
import { formatCurrency, formatDate, formatDateTime, formatDuration, formatNumber, formatRelative } from "@/lib/format";
import { useStudentAccess, useStudentActivity, useStudentPayments } from "@/hooks/use-students";
import { DataTable, type DataTableColumn } from "@/components/shared/data-table";
import { StatCard } from "@/components/shared/stat-card";
import { StatCardsSkeleton } from "@/components/shared/loading-skeleton";
import { AccessStatusBadge, PaymentStatusBadge } from "@/components/shared/status-badge";
import { ProgressBar } from "@/components/shared/progress-bar";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// ---------------------------------------------------------------------------
// Overview
// ---------------------------------------------------------------------------

function InfoRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid gap-1 py-3 text-sm sm:grid-cols-[12rem_1fr] sm:gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

export function StudentOverviewTab({ student }: { student: Student }) {
  const access = useStudentAccess(student.id);
  const records = access.data ?? [];
  const avgProgress = records.length
    ? Math.round(records.reduce((sum, r) => sum + r.progress, 0) / records.length)
    : 0;

  return (
    <div className="space-y-6">
      {access.isLoading ? (
        <StatCardsSkeleton count={4} className="sm:grid-cols-2 xl:grid-cols-4" />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Courses enrolled" value={formatNumber(student.enrolledCourseIds.length)} icon={BookOpen} />
          <StatCard label="Active access" value={formatNumber(student.activeAccessCount)} icon={KeyRound} />
          <StatCard label="Total spent" value={formatCurrency(student.totalSpent)} icon={Wallet} />
          <StatCard
            label="Avg. progress"
            value={access.error ? "—" : `${avgProgress}%`}
            icon={LineChart}
            hint={access.error ? "Couldn't load progress" : `Across ${records.length} course${records.length === 1 ? "" : "s"}`}
          />
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>
            <h2 className="text-base font-semibold">Account information</h2>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="divide-y">
            <InfoRow label="Full name">{student.name}</InfoRow>
            <InfoRow label="Email">{student.email}</InfoRow>
            <InfoRow label="Phone">{student.phone ?? <span className="text-muted-foreground">Not provided</span>}</InfoRow>
            <InfoRow label="Account status">{STUDENT_STATUS[student.status].label}</InfoRow>
            <InfoRow label="Two-factor authentication">{student.twoFactorEnabled ? "Enabled" : "Not enabled"}</InfoRow>
            <InfoRow label="Joined">
              <span className="tabular-nums">{formatDateTime(student.createdAt)}</span>
            </InfoRow>
            <InfoRow label="Last login">
              <span className="tabular-nums">
                {student.lastLoginAt ? `${formatDateTime(student.lastLoginAt)} (${formatRelative(student.lastLoginAt)})` : "Never"}
              </span>
            </InfoRow>
            <InfoRow label="Student ID">
              <span className="font-mono text-xs">{student.id}</span>
            </InfoRow>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Access
// ---------------------------------------------------------------------------

const accessColumns: DataTableColumn<AccessRecord>[] = [
  {
    id: "course",
    header: "Course",
    cell: (r) => <span className="line-clamp-2 font-medium">{r.courseName}</span>,
    className: "min-w-48 max-w-72 whitespace-normal",
  },
  { id: "status", header: "Access", cell: (r) => <AccessStatusBadge status={r.status} /> },
  { id: "payment", header: "Payment", cell: (r) => <PaymentStatusBadge status={r.paymentStatus} />, hideBelow: "md" },
  {
    id: "granted",
    header: "Granted",
    cell: (r) => <span className="text-muted-foreground tabular-nums">{formatDate(r.grantedAt)}</span>,
    hideBelow: "lg",
  },
  {
    id: "expires",
    header: "Expires",
    cell: (r) => (
      <span className="text-muted-foreground tabular-nums">
        {r.expiresAt ? formatDate(r.expiresAt) : r.status === "active" ? "Lifetime" : "—"}
      </span>
    ),
    hideBelow: "lg",
  },
  {
    id: "progress",
    header: "Progress",
    cell: (r) => <ProgressBar value={r.progress} label={`${r.courseName} progress`} />,
    className: "min-w-36",
    hideBelow: "sm",
  },
];

export function StudentAccessTab({ studentId }: { studentId: ID }) {
  const query = useStudentAccess(studentId);
  return (
    <DataTable
      columns={accessColumns}
      data={query.data}
      getRowId={(r) => r.id}
      isLoading={query.isLoading}
      isFetching={query.isFetching}
      error={query.error}
      onRetry={() => query.refetch()}
      emptyIcon={KeyRound}
      emptyTitle="No course access yet"
      emptyDescription="Course access records appear here once the student registers for a course."
      caption="Course access"
    />
  );
}

// ---------------------------------------------------------------------------
// Payments
// ---------------------------------------------------------------------------

const paymentColumns: DataTableColumn<Payment>[] = [
  {
    id: "course",
    header: "Course",
    cell: (p) => <span className="line-clamp-2 font-medium">{p.courseName}</span>,
    className: "min-w-48 max-w-72 whitespace-normal",
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
    cell: (p) => <span className="font-mono text-xs text-muted-foreground">{p.transactionId}</span>,
    hideBelow: "lg",
  },
  { id: "method", header: "Method", cell: (p) => <span className="text-muted-foreground">{p.method}</span>, hideBelow: "md" },
  {
    id: "date",
    header: "Date",
    cell: (p) => <span className="text-muted-foreground tabular-nums">{formatDate(p.createdAt)}</span>,
    hideBelow: "sm",
  },
];

export function StudentPaymentsTab({ studentId }: { studentId: ID }) {
  const query = useStudentPayments(studentId);
  return (
    <DataTable
      columns={paymentColumns}
      data={query.data}
      getRowId={(p) => p.id}
      isLoading={query.isLoading}
      isFetching={query.isFetching}
      error={query.error}
      onRetry={() => query.refetch()}
      emptyIcon={CreditCard}
      emptyTitle="No payments yet"
      emptyDescription="Payments made by this student will appear here."
      caption="Payments"
    />
  );
}

// ---------------------------------------------------------------------------
// Learning activity
// ---------------------------------------------------------------------------

const activityColumns: DataTableColumn<LearningActivity>[] = [
  {
    id: "course",
    header: "Course",
    cell: (a) => <span className="line-clamp-2 font-medium">{a.courseName}</span>,
    className: "min-w-44 max-w-64 whitespace-normal",
  },
  {
    id: "resource",
    header: "Resource",
    cell: (a) => (
      <div className="min-w-0">
        <p className="line-clamp-1">{a.resourceName}</p>
        <p className="text-xs text-muted-foreground tabular-nums">
          Page {a.lastPage} of {a.pageCount}
        </p>
      </div>
    ),
    className: "min-w-44 max-w-64 whitespace-normal",
    hideBelow: "md",
  },
  {
    id: "progress",
    header: "Progress",
    cell: (a) => <ProgressBar value={a.progress} label={`${a.resourceName} progress`} />,
    className: "min-w-36",
  },
  {
    id: "time",
    header: "Time Spent",
    align: "right",
    cell: (a) => <span className="tabular-nums">{formatDuration(a.timeSpentMinutes)}</span>,
    hideBelow: "lg",
  },
  {
    id: "last",
    header: "Last Accessed",
    cell: (a) => (
      <span className="text-muted-foreground tabular-nums" title={formatDateTime(a.lastAccessedAt)}>
        {formatRelative(a.lastAccessedAt)}
      </span>
    ),
    hideBelow: "sm",
  },
];

export function StudentActivityTab({ studentId }: { studentId: ID }) {
  const query = useStudentActivity(studentId);
  return (
    <DataTable
      columns={activityColumns}
      data={query.data}
      getRowId={(a) => a.id}
      isLoading={query.isLoading}
      isFetching={query.isFetching}
      error={query.error}
      onRetry={() => query.refetch()}
      emptyIcon={Activity}
      emptyTitle="No learning activity yet"
      emptyDescription="Reading progress appears here once the student opens a course resource."
      caption="Learning activity"
    />
  );
}
