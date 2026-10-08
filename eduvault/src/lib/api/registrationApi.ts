/**
 * Registration API — real backend endpoints.
 *
 * Admin registrations (mounted at /api/admin/students/registrations/):
 *   GET  /api/admin/students/registrations/         → paginated list
 *   GET  /api/admin/students/registrations/:id/     → detail
 *   POST /api/admin/students/registrations/:id/approve/ → approve (immediate access)
 *   POST /api/admin/students/registrations/:id/reject/  → reject
 *
 * Student registration request (access is requested via the access app):
 *   POST /api/student/access/ → create an access request for a course
 *
 * Note: The backend's "registration" concept is student account approval.
 * "Course access requests" are handled by the access app.
 * The RegistrationStatus mapping:
 *   "immediate_access" → approve
 *   other (reject/pending) → reject
 */
import type { ID, PaginatedResponse, Registration, RegistrationListParams, RegistrationStatus } from "@/types";
import { http } from "./client";

export interface RegistrationApi {
  list(params?: RegistrationListParams): Promise<PaginatedResponse<Registration>>;
  get(id: ID): Promise<Registration>;
  /** Admin decision: approve (immediate_access) or reject. */
  updateStatus(id: ID, status: RegistrationStatus, note?: string): Promise<Registration>;
  /** Student: request access to a course. */
  requestAccess(courseId: ID, message?: string): Promise<Registration>;
}

export const registrationApi: RegistrationApi = {
  list: (params) => http.get("/admin/students/registrations/", { params: { ...params } }),
  get: (id) => http.get(`/admin/students/registrations/${id}/`),

  async updateStatus(id, status, note) {
    if (status === "immediate_access") {
      return http.post(`/admin/students/registrations/${id}/approve/`);
    }
    // "payment_required" or "pending" treated as rejection
    return http.post(`/admin/students/registrations/${id}/reject/`, { reason: note ?? "" });
  },

  // Course access requests go through the access app
  requestAccess: (courseId) => http.post("/student/access/", { course: courseId }),
};
