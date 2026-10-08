import { cn } from "@/lib/utils";
import {
  ACCESS_STATUS,
  AUDIT_STATUS,
  COURSE_STATUS,
  PAYMENT_STATUS,
  REGISTRATION_STATUS,
  RESOURCE_STATUS,
  STUDENT_STATUS,
  type StatusMeta,
  type StatusTone,
} from "@/lib/constants";
import type {
  AuditStatus,
  CourseStatus,
  PaymentStatus,
  RegistrationStatus,
  ResourceStatus,
  StudentCourseAccess,
  StudentStatus,
} from "@/types";

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "bg-muted text-muted-foreground ring-border",
  info: "bg-info/10 text-info ring-info/20",
  success: "bg-success/10 text-success ring-success/20",
  warning: "bg-warning/10 text-warning ring-warning/25",
  danger: "bg-destructive/10 text-destructive ring-destructive/20",
  primary: "bg-primary/10 text-primary ring-primary/20",
};

const DOT_CLASSES: Record<StatusTone, string> = {
  neutral: "bg-muted-foreground/60",
  info: "bg-info",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-destructive",
  primary: "bg-primary",
};

interface StatusBadgeProps {
  label: string;
  tone?: StatusTone;
  dot?: boolean;
  className?: string;
}

/** Base status pill. Prefer the typed wrappers below. */
export function StatusBadge({ label, tone = "neutral", dot = true, className }: StatusBadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex h-6 shrink-0 items-center gap-1.5 rounded-full px-2.5 text-xs font-medium whitespace-nowrap ring-1 ring-inset",
        TONE_CLASSES[tone],
        className,
      )}
    >
      {dot && <span aria-hidden className={cn("size-1.5 rounded-full", DOT_CLASSES[tone])} />}
      {label}
    </span>
  );
}

function fromMeta(meta: StatusMeta, className?: string) {
  return <StatusBadge label={meta.label} tone={meta.tone} className={className} />;
}

export function AccessStatusBadge({ status, className }: { status: StudentCourseAccess; className?: string }) {
  return fromMeta(ACCESS_STATUS[status], className);
}

export function PaymentStatusBadge({
  status,
  className,
}: {
  status: PaymentStatus | "not_required" | "not_started";
  className?: string;
}) {
  return fromMeta(PAYMENT_STATUS[status], className);
}

export function RegistrationStatusBadge({ status, className }: { status: RegistrationStatus; className?: string }) {
  return fromMeta(REGISTRATION_STATUS[status], className);
}

export function StudentStatusBadge({ status, className }: { status: StudentStatus; className?: string }) {
  return fromMeta(STUDENT_STATUS[status], className);
}

export function CourseStatusBadge({ status, className }: { status: CourseStatus; className?: string }) {
  return fromMeta(COURSE_STATUS[status], className);
}

export function ResourceStatusBadge({ status, className }: { status: ResourceStatus; className?: string }) {
  return fromMeta(RESOURCE_STATUS[status], className);
}

export function AuditStatusBadge({ status, className }: { status: AuditStatus; className?: string }) {
  return fromMeta(AUDIT_STATUS[status], className);
}
