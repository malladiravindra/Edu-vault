/**
 * Student API — real backend endpoints.
 *
 * Admin student endpoints (all under /api/admin/students/):
 *   GET  /api/admin/students/           → paginated student list
 *   GET  /api/admin/students/:id/       → student detail
 *   POST /api/admin/students/:id/suspend/   → suspend
 *   POST /api/admin/students/:id/reinstate/ → reinstate
 *
 * Current-student endpoints (under /api/student/ and /api/accounts/):
 *   GET   /api/student/profile/          → own profile
 *   PATCH /api/student/profile/          → update profile
 *   POST  /api/accounts/password-change/ → change password
 *   GET   /api/student/dashboard/        → dashboard stats
 */
import type {
  AccessRecord,
  ID,
  LearningActivity,
  PaginatedResponse,
  Payment,
  Student,
  StudentDashboardData,
  StudentListParams,
} from "@/types";
import { http } from "./client";
import { mapUser } from "./authApi";

export interface ProfileUpdate {
  name: string;
  phone?: string;
}

export interface ChangePasswordInput {
  currentPassword: string;
  newPassword: string;
}

export interface StudentApi {
  // Admin
  list(params?: StudentListParams): Promise<PaginatedResponse<Student>>;
  get(id: ID): Promise<Student>;
  suspend(id: ID, reason?: string): Promise<Student>;
  reinstate(id: ID): Promise<Student>;
  getAccess(id: ID): Promise<AccessRecord[]>;
  getPayments(id: ID): Promise<Payment[]>;
  getActivity(id: ID): Promise<LearningActivity[]>;
  // Current student
  getProfile(): Promise<Student>;
  updateProfile(input: ProfileUpdate): Promise<Student>;
  changePassword(input: ChangePasswordInput): Promise<void>;
  getDashboard(): Promise<StudentDashboardData>;
}

export const studentApi: StudentApi = {
  // Admin
  list: (params) =>
    http.get<PaginatedResponse<Record<string, unknown>>>("/admin/students/", { params: { ...params } }).then((res) => ({
      ...res,
      data: (res.data ?? []).map((u) => mapUser(u) as Student),
    })),

  get: (id) => http.get<Record<string, unknown>>(`/admin/students/${id}/`).then((u) => mapUser(u) as Student),
  suspend: (id, reason) =>
    http.post<Record<string, unknown>>(`/admin/students/${id}/suspend/`, { reason }).then((u) => mapUser(u) as Student),
  reinstate: (id) =>
    http.post<Record<string, unknown>>(`/admin/students/${id}/reinstate/`).then((u) => mapUser(u) as Student),

  async getAccess(id) {
    const res = await http.get<PaginatedResponse<AccessRecord>>("/admin/students/access/", {
      params: { student: id, page_size: 100 },
    });
    return res.data ?? [];
  },

  async getPayments(id) {
    const res = await http.get<PaginatedResponse<Payment>>("/admin/students/payments/", {
      params: { student: id, page_size: 100 },
    });
    return res.data ?? [];
  },

  getActivity: () => Promise.resolve([]),

  // Current student
  getProfile: () => http.get<Record<string, unknown>>("/student/profile/").then((u) => mapUser(u) as Student),

  updateProfile: (input) =>
    http
      .patch<Record<string, unknown>>("/student/profile/", { full_name: input.name, phone_number: input.phone })
      .then((u) => mapUser(u) as Student),

  changePassword: (input) =>
    http.post("/accounts/password-change/", {
      current_password: input.currentPassword,
      new_password: input.newPassword,
    }),

  async getDashboard(): Promise<StudentDashboardData> {
    const raw = await http.get<{
      active_courses?: Array<{ title?: string; progress_percent?: number }>;
      pending_requests?: unknown[];
      learning_stats?: {
        total_courses?: number;
        active_courses?: number;
        reading_minutes?: number;
      };
    }>("/student/dashboard/");

    const activeCourses = raw?.active_courses ?? [];
    const overallProgress =
      activeCourses.length > 0
        ? Math.round(
            activeCourses.reduce((sum, c) => sum + (c.progress_percent ?? 0), 0) / activeCourses.length,
          )
        : 0;

    const weeklyMinutes = [
      { label: "Mon", value: 0 },
      { label: "Tue", value: 0 },
      { label: "Wed", value: 0 },
      { label: "Thu", value: 0 },
      { label: "Fri", value: 0 },
      { label: "Sat", value: 0 },
      { label: "Sun", value: 0 },
    ];
    const readingMins = Math.round(raw?.learning_stats?.reading_minutes ?? 0);
    const todayIndex = (new Date().getDay() + 6) % 7; // Monday is 0
    weeklyMinutes[todayIndex].value = readingMins;

    return {
      myCoursesCount: raw?.learning_stats?.total_courses ?? activeCourses.length,
      activeCoursesCount: raw?.learning_stats?.active_courses ?? activeCourses.length,
      pendingRequestsCount: raw?.pending_requests?.length ?? 0,
      overallProgress,
      weeklyMinutes,
      ...raw,
    };
  },
};
