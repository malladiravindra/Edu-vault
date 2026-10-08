"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { ArrowLeft, Ban, RotateCcw, ShieldCheck, ShieldOff, UserX } from "lucide-react";
import type { ID, Student } from "@/types";
import { ApiError } from "@/lib/api/client";
import { formatCurrency, formatDate, formatRelative } from "@/lib/format";
import { useStudent } from "@/hooks/use-students";
import { useBreadcrumbLabel } from "@/components/layout/breadcrumbs";
import { PageHeader } from "@/components/shared/page-header";
import { DetailSkeleton } from "@/components/shared/loading-skeleton";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { StudentStatusBadge } from "@/components/shared/status-badge";
import { UserAvatar } from "@/components/shared/user-avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { StudentStatusDialog } from "./student-status-dialog";
import { StudentAccessTab, StudentActivityTab, StudentOverviewTab, StudentPaymentsTab } from "./student-detail-tabs";

function BackLink() {
  return (
    <Link
      href="/admin/students"
      className="inline-flex items-center gap-1 rounded text-sm text-muted-foreground hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
    >
      <ArrowLeft className="size-4" aria-hidden />
      Back to students
    </Link>
  );
}

function Meta({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium tabular-nums">{children}</dd>
    </div>
  );
}

export function StudentDetailView({ id }: { id: ID }) {
  const query = useStudent(id);
  const student = query.data;
  const [dialogOpen, setDialogOpen] = useState(false);
  // Snapshot so the dialog copy doesn't flip while it animates closed after the mutation.
  const [target, setTarget] = useState<Student | null>(null);
  const [tab, setTab] = useState("overview");

  useBreadcrumbLabel(id, student?.name);

  if (query.isLoading) return <DetailSkeleton />;

  if (query.error instanceof ApiError && query.error.status === 404) {
    return (
      <div className="space-y-6">
        <BackLink />
        <Card>
          <EmptyState
            icon={UserX}
            title="Student not found"
            description="This student may have been removed, or the link is incorrect."
            action={
              <Button variant="outline" size="sm" nativeButton={false} render={<Link href="/admin/students" />}>
                Back to students
              </Button>
            }
          />
        </Card>
      </div>
    );
  }

  if (query.error || !student) {
    return (
      <div className="space-y-6">
        <BackLink />
        <Card>
          <ErrorState
            title="We couldn't load this student"
            error={query.error}
            onRetry={() => query.refetch()}
            retrying={query.isFetching}
          />
        </Card>
      </div>
    );
  }

  const isSuspended = student.status === "suspended";
  const openStatusDialog = () => {
    setTarget(student);
    setDialogOpen(true);
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={<BackLink />}
        title={student.name}
        description="Student profile, course access, payments and learning activity."
        actions={
          isSuspended ? (
            <Button variant="outline" onClick={openStatusDialog}>
              <RotateCcw />
              Reinstate
            </Button>
          ) : (
            <Button variant="destructive" onClick={openStatusDialog}>
              <Ban />
              Suspend
            </Button>
          )
        }
      />

      <Card>
        <CardContent className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-4">
            <UserAvatar name={student.name} src={student.avatarUrl} size="lg" />
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="truncate text-lg font-semibold">{student.name}</h2>
                <StudentStatusBadge status={student.status} />
              </div>
              <p className="truncate text-sm text-muted-foreground">{student.email}</p>
            </div>
          </div>
          <dl className="grid grid-cols-2 gap-x-8 gap-y-4 sm:grid-cols-4">
            <Meta label="Joined">{formatDate(student.createdAt)}</Meta>
            <Meta label="Last login">{student.lastLoginAt ? formatRelative(student.lastLoginAt) : "Never"}</Meta>
            <Meta label="Two-factor">
              {student.twoFactorEnabled ? (
                <span className="inline-flex items-center gap-1 text-success">
                  <ShieldCheck className="size-4" aria-hidden />
                  Enabled
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 text-muted-foreground">
                  <ShieldOff className="size-4" aria-hidden />
                  Off
                </span>
              )}
            </Meta>
            <Meta label="Total spent">{formatCurrency(student.totalSpent)}</Meta>
          </dl>
        </CardContent>
      </Card>

      <Tabs value={tab} onValueChange={(v) => setTab(String(v))} className="gap-4">
        <div className="overflow-x-auto border-b">
          <TabsList variant="line" aria-label="Student sections">
            <TabsTrigger value="overview" className="px-3">
              Overview
            </TabsTrigger>
            <TabsTrigger value="access" className="px-3">
              Access
            </TabsTrigger>
            <TabsTrigger value="payments" className="px-3">
              Payments
            </TabsTrigger>
            <TabsTrigger value="activity" className="px-3">
              Learning Activity
            </TabsTrigger>
          </TabsList>
        </div>
        <TabsContent value="overview">
          <StudentOverviewTab student={student} />
        </TabsContent>
        <TabsContent value="access">
          <StudentAccessTab studentId={student.id} />
        </TabsContent>
        <TabsContent value="payments">
          <StudentPaymentsTab studentId={student.id} />
        </TabsContent>
        <TabsContent value="activity">
          <StudentActivityTab studentId={student.id} />
        </TabsContent>
      </Tabs>

      <StudentStatusDialog student={target} open={dialogOpen} onOpenChange={setDialogOpen} />
    </div>
  );
}
