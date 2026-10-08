import type {
  AccessListParams,
  AuditLogListParams,
  CourseListParams,
  ID,
  LearningHistoryParams,
  NotificationListParams,
  PaymentListParams,
  RegistrationListParams,
  ReportFilters,
  ReportType,
  StudentListParams,
} from "@/types";
import type { StudentCatalogParams } from "@/lib/api/courseApi";
import type { NotificationScope } from "@/lib/api/notificationApi";

/** Central query-key factory so invalidation stays consistent across hooks. */
export const queryKeys = {
  auth: { me: ["auth", "me"] as const },
  dashboard: {
    admin: ["dashboard", "admin"] as const,
    student: ["dashboard", "student"] as const,
  },
  courses: {
    all: ["courses"] as const,
    list: (params: CourseListParams) => ["courses", "list", params] as const,
    detail: (id: ID) => ["courses", "detail", id] as const,
    categories: ["courses", "categories"] as const,
    catalog: (params: StudentCatalogParams) => ["courses", "catalog", params] as const,
    studentDetail: (id: ID) => ["courses", "student", id] as const,
    mine: ["courses", "mine"] as const,
  },
  resources: {
    all: ["resources"] as const,
    byCourse: (courseId: ID) => ["resources", "course", courseId] as const,
    published: (courseId: ID) => ["resources", "published", courseId] as const,
    session: (resourceId: ID, mode: string) => ["resources", "session", resourceId, mode] as const,
    page: (resourceId: ID, page: number) => ["resources", "page", resourceId, page] as const,
  },
  students: {
    all: ["students"] as const,
    list: (params: StudentListParams) => ["students", "list", params] as const,
    detail: (id: ID) => ["students", "detail", id] as const,
    access: (id: ID) => ["students", "detail", id, "access"] as const,
    payments: (id: ID) => ["students", "detail", id, "payments"] as const,
    activity: (id: ID) => ["students", "detail", id, "activity"] as const,
    profile: ["students", "profile"] as const,
  },
  registrations: {
    all: ["registrations"] as const,
    list: (params: RegistrationListParams) => ["registrations", "list", params] as const,
    detail: (id: ID) => ["registrations", "detail", id] as const,
  },
  access: {
    all: ["access"] as const,
    list: (params: AccessListParams) => ["access", "list", params] as const,
    summary: ["access", "summary"] as const,
  },
  payments: {
    all: ["payments"] as const,
    list: (params: PaymentListParams) => ["payments", "list", params] as const,
    mine: (params: PaymentListParams) => ["payments", "mine", params] as const,
    checkout: (courseId: ID) => ["payments", "checkout", courseId] as const,
  },
  notifications: {
    all: (scope: NotificationScope) => ["notifications", scope] as const,
    list: (scope: NotificationScope, params: NotificationListParams) => ["notifications", scope, "list", params] as const,
    unread: (scope: NotificationScope) => ["notifications", scope, "unread"] as const,
  },
  reports: {
    detail: (type: ReportType, filters: ReportFilters) => ["reports", type, filters] as const,
  },
  auditLogs: {
    list: (params: AuditLogListParams) => ["audit-logs", params] as const,
  },
  settings: ["settings"] as const,
  learning: {
    all: ["learning"] as const,
    history: (params: LearningHistoryParams) => ["learning", "history", params] as const,
    recent: (limit: number) => ["learning", "recent", limit] as const,
  },
};
