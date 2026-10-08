"use client";

import type { ReactNode } from "react";
import type { Registration, RegistrationStatus } from "@/types";
import { formatDateTime } from "@/lib/format";
import { useRegistration } from "@/hooks/use-registrations";
import { SideDrawer } from "@/components/shared/side-drawer";
import { RegistrationStatusBadge } from "@/components/shared/status-badge";
import { UserAvatar } from "@/components/shared/user-avatar";
import { ErrorState } from "@/components/shared/error-state";
import { ListSkeleton } from "@/components/shared/loading-skeleton";
import { Button } from "@/components/ui/button";
import { DECISION_LABEL, DECISION_ORDER } from "./registration-decision-dialog";

interface RegistrationDrawerProps {
  /** Row the drawer was opened from; shown instantly while the detail query loads. */
  registration: Registration | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDecide: (registration: Registration, status: RegistrationStatus) => void;
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-3 py-2.5 text-sm">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

export function RegistrationDrawer({ registration, open, onOpenChange, onDecide }: RegistrationDrawerProps) {
  const query = useRegistration(open ? registration?.id : undefined);
  const reg = query.data ?? registration;

  let body: ReactNode;
  if (!reg && query.isLoading) {
    body = <ListSkeleton rows={3} />;
  } else if (!reg) {
    body = <ErrorState compact error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />;
  } else {
    body = (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <UserAvatar name={reg.studentName} size="lg" />
          <div className="min-w-0">
            <p className="truncate font-semibold">{reg.studentName}</p>
            <p className="truncate text-sm text-muted-foreground">{reg.studentEmail}</p>
          </div>
        </div>

        <dl className="divide-y">
          <DetailRow label="Status">
            <RegistrationStatusBadge status={reg.status} />
          </DetailRow>
          <DetailRow label="Email">{reg.studentEmail}</DetailRow>
          <DetailRow label="Course">
            <span className="font-medium">{reg.courseName}</span>
          </DetailRow>
          <DetailRow label="Submitted">
            <span className="tabular-nums">{formatDateTime(reg.createdAt)}</span>
          </DetailRow>
          <DetailRow label="Reviewed by">{reg.reviewedBy ?? <span className="text-muted-foreground">Not reviewed yet</span>}</DetailRow>
          <DetailRow label="Reviewed at">
            <span className="tabular-nums">{formatDateTime(reg.reviewedAt)}</span>
          </DetailRow>
        </dl>

        <section className="space-y-2">
          <h3 className="text-sm font-medium">Message from student</h3>
          {reg.message ? (
            <p className="rounded-lg border bg-muted/40 p-3 text-sm whitespace-pre-line">{reg.message}</p>
          ) : (
            <p className="text-sm text-muted-foreground">No message was included with this request.</p>
          )}
        </section>
      </div>
    );
  }

  const footer = reg ? (
    <div className="flex flex-col gap-2">
      {DECISION_ORDER.map((status) => (
        <Button
          key={status}
          variant={status === "immediate_access" ? "default" : "outline"}
          disabled={reg.status === status}
          onClick={() => onDecide(reg, status)}
        >
          {DECISION_LABEL[status]}
          {reg.status === status && <span className="text-xs opacity-70">(current)</span>}
        </Button>
      ))}
    </div>
  ) : undefined;

  return (
    <SideDrawer
      open={open}
      onOpenChange={onOpenChange}
      title="Registration details"
      description={reg ? `Request for ${reg.courseName}` : undefined}
      footer={footer}
    >
      {body}
    </SideDrawer>
  );
}
