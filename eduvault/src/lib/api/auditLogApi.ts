/**
 * Audit Log API — real backend endpoints.
 *
 *   GET /api/admin/audit-logs/        → paginated list
 *   GET /api/admin/audit-logs/:id/    → detail (not used by frontend currently)
 */
import type { AuditLog, AuditLogListParams, PaginatedResponse } from "@/types";
import { http } from "./client";

export interface AuditLogApi {
  list(params?: AuditLogListParams): Promise<PaginatedResponse<AuditLog>>;
}

export const auditLogApi: AuditLogApi = {
  list: (params) => http.get("/admin/audit-logs/", { params: { ...params } }),
};
