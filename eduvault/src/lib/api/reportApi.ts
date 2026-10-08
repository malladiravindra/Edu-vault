/**
 * Report API — real backend endpoints.
 *
 * All under /api/admin/reports/:
 *   GET /api/admin/reports/dashboard/  → admin dashboard stats
 *   GET /api/admin/reports/overview/   → overall overview report
 *   GET /api/admin/reports/users/      → user/registration report
 *   GET /api/admin/reports/courses/    → course popularity report (paginated)
 *   GET /api/admin/reports/access/     → access distribution report
 *   GET /api/admin/reports/payments/   → revenue / payments report
 *   GET /api/admin/reports/activity/   → learning activity report
 */
import type {
  AdminDashboardData,
  AdminDashboardStats,
  ExportFormat,
  Report,
  ReportFilters,
  ReportType,
} from "@/types";
import { http } from "./client";

export interface ReportApi {
  getAdminDashboard(): Promise<AdminDashboardData>;
  getReport(type: ReportType, filters?: ReportFilters): Promise<Report>;
  exportReport(type: ReportType, format: ExportFormat, filters?: ReportFilters): Promise<{ downloadUrl: string }>;
}

const REPORT_TYPE_TO_PATH: Record<ReportType, string> = {
  registrations: "users",
  revenue: "payments",
  course_popularity: "courses",
  access_distribution: "access",
};

export const reportApi: ReportApi = {
  async getAdminDashboard(): Promise<AdminDashboardData> {
    const raw = await http.get<{
      users?: { students?: number; active?: number; pending_registrations?: number };
      courses?: { published?: number };
      access?: { active?: number };
      payments?: { total_paid?: string };
    }>("/admin/reports/dashboard/");

    const totalStudents = raw?.users?.students ?? 0;
    const activeStudents = raw?.users?.active ?? 0;
    const pendingRegistrations = raw?.users?.pending_registrations ?? 0;
    const activeCourses = raw?.courses?.published ?? 0;
    const activeAccess = raw?.access?.active ?? 0;
    const revenue = Math.round(parseFloat(raw?.payments?.total_paid ?? "0") * 100);

    const stats: AdminDashboardStats = {
      totalStudents,
      activeStudents,
      pendingRegistrations,
      activeCourses,
      activeAccess,
      revenue,
      trends: {
        totalStudents: 0,
        activeStudents: 0,
        pendingRegistrations: 0,
        activeCourses: 0,
        activeAccess: 0,
        revenue: 0,
      },
    };

    return {
      stats,
      registrationsOverview: [],
      revenueOverview: [],
      coursePopularity: [],
      ...raw,
    };
  },

  getReport: (type, filters) => {
    const path = REPORT_TYPE_TO_PATH[type] ?? type;
    return http.get(`/admin/reports/${path}/`, { params: { ...filters } });
  },

  exportReport: (type) =>
    Promise.resolve({ downloadUrl: `#export-not-implemented-${type}` }),
};
