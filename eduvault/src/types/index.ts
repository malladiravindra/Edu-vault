/**
 * EduVault domain types.
 *
 * These mirror the REST contract the backend is expected to expose.
 * Dates are ISO-8601 strings (as they arrive over JSON); money is in minor
 * units (cents) to avoid floating point errors.
 */

export type ID = string;
export type ISODateString = string;

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

export type UserRole = "admin" | "student";

export interface User {
  id: ID;
  name: string;
  email: string;
  role: UserRole;
  avatarUrl?: string;
  twoFactorEnabled: boolean;
  createdAt: ISODateString;
  lastLoginAt?: ISODateString;
}

export interface Admin extends User {
  role: "admin";
  title: string;
}

export type StudentStatus = "active" | "pending" | "suspended";

export interface Student extends User {
  role: "student";
  status: StudentStatus;
  phone?: string;
  enrolledCourseIds: ID[];
  activeAccessCount: number;
  totalSpent: number;
}

export type CurrentUser = Admin | Student;

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface LoginRequest {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface LoginResponse {
  /** When true the client must complete 2FA before the session is active. */
  requiresTwoFactor: boolean;
  /** Short-lived challenge token for the 2FA step. */
  challengeId?: string;
  user?: CurrentUser;
}

export interface RegisterRequest {
  name: string;
  email: string;
  password: string;
  acceptTerms: boolean;
  phone?: string;
  otp?: string;
}

export interface TwoFactorRequest {
  challengeId: string;
  code: string;
}

export interface ResetPasswordRequest {
  token: string;
  password: string;
}

// ---------------------------------------------------------------------------
// Courses & resources
// ---------------------------------------------------------------------------

export type CourseStatus = "draft" | "published" | "archived";

/** free: instant access · paid: payment required · approval: admin approval required */
export type AccessModel = "free" | "paid" | "approval";

export interface Course {
  id: ID;
  name: string;
  slug: string;
  description: string;
  shortDescription: string;
  category: string;
  imageUrl?: string;
  /** Price in minor units (cents). 0 for free courses. */
  price: number;
  currency: string;
  accessModel: AccessModel;
  /** Access duration in days. `null` means lifetime access. */
  accessDurationDays: number | null;
  status: CourseStatus;
  resourceCount: number;
  enrolledCount: number;
  instructor: string;
  createdAt: ISODateString;
  updatedAt: ISODateString;
}

export interface CourseInput {
  name: string;
  description: string;
  shortDescription: string;
  category: string;
  price: number;
  accessModel: AccessModel;
  accessDurationDays: number | null;
  status: CourseStatus;
}

export type ResourceType = "pdf";
export type ResourceStatus = "draft" | "published" | "processing";

export interface Resource {
  id: ID;
  courseId: ID;
  name: string;
  description?: string;
  type: ResourceType;
  status: ResourceStatus;
  pageCount: number;
  fileSizeBytes: number;
  order: number;
  createdAt: ISODateString;
  updatedAt: ISODateString;
}

/**
 * Per-page payload for the protected viewer. The backend renders pages
 * server-side and returns short-lived, session-bound image data — never a
 * public PDF URL.
 */
export interface ResourcePage {
  resourceId: ID;
  pageNumber: number;
  /** Short-lived signed image URL or data URI. `null` while mock rendering. */
  imageSrc: string | null;
  width: number;
  height: number;
}

export interface ResourceViewerSession {
  resourceId: ID;
  courseId: ID;
  resourceName: string;
  courseName: string;
  pageCount: number;
  /** Watermark text is supplied by the server so it can't be tampered with. */
  watermark: {
    name: string;
    email: string;
    label: string;
  };
  expiresAt: ISODateString;
}

// ---------------------------------------------------------------------------
// Registrations & access
// ---------------------------------------------------------------------------

export type RegistrationStatus = "pending" | "immediate_access" | "payment_required";

export interface Registration {
  id: ID;
  studentId: ID;
  studentName: string;
  studentEmail: string;
  courseId: ID;
  courseName: string;
  status: RegistrationStatus;
  message?: string;
  createdAt: ISODateString;
  reviewedAt?: ISODateString;
  reviewedBy?: string;
}

export type AccessStatus = "pending" | "payment_required" | "active" | "expired" | "suspended";

export interface AccessRecord {
  id: ID;
  studentId: ID;
  studentName: string;
  studentEmail: string;
  courseId: ID;
  courseName: string;
  status: AccessStatus;
  paymentStatus: PaymentStatus | "not_required";
  grantedAt?: ISODateString;
  expiresAt?: ISODateString;
  progress: number;
  createdAt: ISODateString;
}

/** Access state from the student's point of view (includes "none"). */
export type StudentCourseAccess = AccessStatus | "none";

export interface StudentCourse extends Course {
  access: StudentCourseAccess;
  accessRecordId?: ID;
  progress: number;
  /** When the student requested access (pending / payment required). */
  requestedAt?: ISODateString;
  expiresAt?: ISODateString;
  lastAccessedAt?: ISODateString;
}

// ---------------------------------------------------------------------------
// Payments
// ---------------------------------------------------------------------------

export type PaymentStatus = "successful" | "pending" | "failed" | "refunded";

export interface Payment {
  id: ID;
  studentId: ID;
  studentName: string;
  studentEmail: string;
  courseId: ID;
  courseName: string;
  /** Amount in minor units (cents). */
  amount: number;
  currency: string;
  status: PaymentStatus;
  transactionId: string;
  method: string;
  createdAt: ISODateString;
}

export interface CheckoutSummary {
  courseId: ID;
  courseName: string;
  subtotal: number;
  tax: number;
  total: number;
  currency: string;
  accessDurationDays: number | null;
  paymentStatus: PaymentStatus | "not_started";
}

export interface CheckoutSession {
  /** Hosted checkout URL returned by the backend (e.g. Stripe Checkout). */
  redirectUrl: string;
  sessionId: string;
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export type NotificationType =
  | "registration"
  | "access"
  | "payment"
  | "course"
  | "resource"
  | "system"
  | "security";

export interface Notification {
  id: ID;
  title: string;
  description: string;
  type: NotificationType;
  read: boolean;
  href?: string;
  createdAt: ISODateString;
}

// ---------------------------------------------------------------------------
// Audit logs
// ---------------------------------------------------------------------------

export type AuditModule =
  | "auth"
  | "registrations"
  | "students"
  | "courses"
  | "resources"
  | "access"
  | "payments"
  | "settings";

export type AuditStatus = "success" | "failure" | "warning";

export interface AuditLog {
  id: ID;
  userName: string;
  userEmail: string;
  userRole: UserRole;
  action: string;
  module: AuditModule;
  description: string;
  status: AuditStatus;
  ipAddress: string;
  createdAt: ISODateString;
}

// ---------------------------------------------------------------------------
// Learning activity
// ---------------------------------------------------------------------------

export interface LearningActivity {
  id: ID;
  studentId: ID;
  courseId: ID;
  courseName: string;
  resourceId: ID;
  resourceName: string;
  /** 0–100 */
  progress: number;
  timeSpentMinutes: number;
  lastPage: number;
  pageCount: number;
  lastAccessedAt: ISODateString;
}

// ---------------------------------------------------------------------------
// Dashboards & reports
// ---------------------------------------------------------------------------

export interface TimeSeriesPoint {
  label: string;
  value: number;
}

export interface MultiSeriesPoint {
  label: string;
  [series: string]: string | number;
}

export interface AdminDashboardStats {
  totalStudents: number;
  activeStudents: number;
  pendingRegistrations: number;
  activeCourses: number;
  activeAccess: number;
  revenue: number;
  /** Percentage change vs previous period, keyed by stat. */
  trends: Record<
    "totalStudents" | "activeStudents" | "pendingRegistrations" | "activeCourses" | "activeAccess" | "revenue",
    number
  >;
}

export interface AdminDashboardData {
  stats: AdminDashboardStats;
  registrationsOverview: MultiSeriesPoint[];
  revenueOverview: TimeSeriesPoint[];
  coursePopularity: TimeSeriesPoint[];
}

export interface StudentDashboardData {
  myCoursesCount: number;
  activeCoursesCount: number;
  pendingRequestsCount: number;
  /** Average progress across active courses, 0–100 */
  overallProgress: number;
  weeklyMinutes: TimeSeriesPoint[];
}

export type ReportType = "registrations" | "revenue" | "course_popularity" | "access_distribution";

export interface ReportFilters {
  from?: ISODateString;
  to?: ISODateString;
  courseId?: ID;
}

export interface ReportRow {
  [column: string]: string | number;
}

export interface Report {
  type: ReportType;
  title: string;
  generatedAt: ISODateString;
  summary: { label: string; value: string }[];
  chart: MultiSeriesPoint[];
  /** Keys present in each chart point besides `label`. */
  series: string[];
  columns: { key: string; label: string }[];
  rows: ReportRow[];
}

export type ExportFormat = "csv" | "xlsx" | "pdf";

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export interface PlatformSettings {
  platformName: string;
  supportEmail: string;
  defaultCurrency: string;
  timezone: string;
  allowSelfRegistration: boolean;
  maintenanceMode: boolean;
}

export interface AccessDefaults {
  defaultAccessModel: AccessModel;
  defaultAccessDurationDays: number | null;
  autoApproveFreeCourses: boolean;
  expiryReminderDays: number;
}

export interface NotificationPreferences {
  emailNewRegistration: boolean;
  emailPaymentReceived: boolean;
  emailAccessExpiring: boolean;
  inAppSystemAlerts: boolean;
  weeklyDigest: boolean;
}

export interface SecuritySettings {
  requireTwoFactorForAdmins: boolean;
  sessionTimeoutMinutes: number;
  maxLoginAttempts: number;
  watermarkEnabled: boolean;
}

export interface AdminSettings {
  platform: PlatformSettings;
  accessDefaults: AccessDefaults;
  notifications: NotificationPreferences;
  security: SecuritySettings;
}

// ---------------------------------------------------------------------------
// API envelopes
// ---------------------------------------------------------------------------

export interface PaginatedResponse<T> {
  data: T[];
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface ListParams {
  page?: number;
  pageSize?: number;
  search?: string;
  sort?: string;
}

export interface DateRangeParams {
  from?: ISODateString;
  to?: ISODateString;
}

export interface StudentListParams extends ListParams {
  status?: StudentStatus;
  courseId?: ID;
}

export interface RegistrationListParams extends ListParams {
  status?: RegistrationStatus;
}

export interface CourseListParams extends ListParams {
  status?: CourseStatus;
  accessModel?: AccessModel;
}

export interface AccessListParams extends ListParams {
  status?: AccessStatus;
  courseId?: ID;
}

export interface PaymentListParams extends ListParams, DateRangeParams {
  status?: PaymentStatus;
  courseId?: ID;
}

export interface AuditLogListParams extends ListParams, DateRangeParams {
  module?: AuditModule;
  status?: AuditStatus;
}

export interface NotificationListParams extends ListParams {
  type?: NotificationType;
  read?: boolean;
}

export interface LearningHistoryParams extends ListParams, DateRangeParams {
  courseId?: ID;
}

export interface ApiErrorBody {
  message: string;
  code?: string;
  fieldErrors?: Record<string, string[]>;
}
