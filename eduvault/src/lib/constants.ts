import type {
  AccessModel,
  AuditModule,
  AuditStatus,
  CourseStatus,
  NotificationType,
  PaymentStatus,
  RegistrationStatus,
  ResourceStatus,
  StudentCourseAccess,
  StudentStatus,
} from "@/types";

export const APP_NAME = "EduVault";

/** Visual tone used by StatusBadge. Keep the palette small and consistent. */
export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger" | "primary";

export interface StatusMeta {
  label: string;
  tone: StatusTone;
}

export const REGISTRATION_STATUS: Record<RegistrationStatus, StatusMeta> = {
  pending: { label: "Pending", tone: "warning" },
  immediate_access: { label: "Immediate Access", tone: "success" },
  payment_required: { label: "Payment Required", tone: "info" },
};

export const ACCESS_STATUS: Record<StudentCourseAccess, StatusMeta> = {
  none: { label: "No Access", tone: "neutral" },
  pending: { label: "Pending", tone: "warning" },
  payment_required: { label: "Payment Required", tone: "info" },
  active: { label: "Active", tone: "success" },
  expired: { label: "Expired", tone: "neutral" },
  suspended: { label: "Suspended", tone: "danger" },
};

export const PAYMENT_STATUS: Record<PaymentStatus | "not_required" | "not_started", StatusMeta> = {
  successful: { label: "Successful", tone: "success" },
  pending: { label: "Pending", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
  refunded: { label: "Refunded", tone: "neutral" },
  not_required: { label: "Not Required", tone: "neutral" },
  not_started: { label: "Not Started", tone: "neutral" },
};

export const STUDENT_STATUS: Record<StudentStatus, StatusMeta> = {
  active: { label: "Active", tone: "success" },
  pending: { label: "Pending", tone: "warning" },
  suspended: { label: "Suspended", tone: "danger" },
};

export const COURSE_STATUS: Record<CourseStatus, StatusMeta> = {
  draft: { label: "Draft", tone: "neutral" },
  published: { label: "Published", tone: "success" },
  archived: { label: "Archived", tone: "warning" },
};

export const RESOURCE_STATUS: Record<ResourceStatus, StatusMeta> = {
  draft: { label: "Unpublished", tone: "neutral" },
  published: { label: "Published", tone: "success" },
  processing: { label: "Processing", tone: "info" },
};

export const AUDIT_STATUS: Record<AuditStatus, StatusMeta> = {
  success: { label: "Success", tone: "success" },
  failure: { label: "Failed", tone: "danger" },
  warning: { label: "Warning", tone: "warning" },
};

export const ACCESS_MODEL_LABEL: Record<AccessModel, string> = {
  free: "Free — instant access",
  paid: "Paid — payment required",
  approval: "Approval — admin review",
};

export const AUDIT_MODULE_LABEL: Record<AuditModule, string> = {
  auth: "Authentication",
  registrations: "Registrations",
  students: "Students",
  courses: "Courses",
  resources: "Resources",
  access: "Access",
  payments: "Payments",
  settings: "Settings",
};

export const NOTIFICATION_TYPE_LABEL: Record<NotificationType, string> = {
  registration: "Registration",
  access: "Access",
  payment: "Payment",
  course: "Course",
  resource: "Resource",
  system: "System",
  security: "Security",
};

/** Builds `{ value, label }` options from a status map, for filters/selects. */
export function toOptions<K extends string>(map: Record<K, StatusMeta | string>): { value: K; label: string }[] {
  return (Object.keys(map) as K[]).map((value) => {
    const meta = map[value];
    return { value, label: typeof meta === "string" ? meta : meta.label };
  });
}

export const DEFAULT_PAGE_SIZE = 10;
