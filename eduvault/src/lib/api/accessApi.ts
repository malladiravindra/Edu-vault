/**
 * Access API — real backend endpoints.
 *
 * Admin access endpoints (under /api/admin/students/access/):
 *   GET   /api/admin/students/access/           → paginated list
 *   GET   /api/admin/students/access/:id/       → detail
 *   PATCH /api/admin/students/access/:id/       → update status / decision
 *   POST  /api/admin/students/access/grant/     → grant new access
 *
 * Student decision (course access request):
 *   POST /api/admin/students/:userId/decision/  → admin decision on a student's course
 *
 * Note: The backend does not have a dedicated /summary/ or /extend/ endpoint.
 * The summary is computed client-side from the list, and "extend" is implemented
 * as a PATCH on the detail record.
 */
import type { AccessListParams, AccessRecord, AccessStatus, ID, PaginatedResponse } from "@/types";
import { http } from "./client";

export interface AccessApi {
  list(params?: AccessListParams): Promise<PaginatedResponse<AccessRecord>>;
  updateStatus(id: ID, status: Extract<AccessStatus, "active" | "suspended">): Promise<AccessRecord>;
  extend(id: ID, days: number): Promise<AccessRecord>;
  /** Counts per status for summary cards — computed from the list. */
  summary(): Promise<Record<AccessStatus, number>>;
}

export const accessApi: AccessApi = {
  list: (params) => http.get("/admin/students/access/", { params: { ...params } }),
  updateStatus: (id, status) => {
    const action = status === "active" ? "approve" : "revoke";
    return http.patch(`/admin/students/access/${id}/`, { action });
  },

  // Backend has no dedicated /extend/ endpoint: PATCH the record.
  extend: (id, days) => http.patch(`/admin/students/access/${id}/`, { extend_days: days }),

  // Backend has no /summary/ endpoint — fetch the full list and aggregate.
  async summary() {
    const counts: Record<AccessStatus, number> = {
      pending: 0,
      payment_required: 0,
      active: 0,
      expired: 0,
      suspended: 0,
    };
    let page = 1;
    while (true) {
      const res = await http.get<PaginatedResponse<AccessRecord>>("/admin/students/access/", {
        params: { page, page_size: 100 },
      });
      const items = res?.data ?? [];
      for (const a of items) counts[a.status] = (counts[a.status] ?? 0) + 1;
      const totalPages = res?.totalPages ?? 1;
      if (page >= totalPages) break;
      page++;
    }
    return counts;
  },
};
