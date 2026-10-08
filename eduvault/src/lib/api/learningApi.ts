/**
 * Learning API — real backend endpoints.
 *
 * All under /api/student/learning-history/ and /api/student/viewing/:
 *
 *   GET  /api/student/learning-history/                       → paginated history
 *   POST /api/student/viewing/resources/:id/activity/         → record progress
 *
 * Note: There is no /recent/ endpoint on the backend. The frontend derives
 * "recent" from the first page of the learning history ordered by last_accessed.
 */
import type { ID, LearningActivity, LearningHistoryParams, PaginatedResponse } from "@/types";
import { http } from "./client";

export interface LearningApi {
  history(params?: LearningHistoryParams): Promise<PaginatedResponse<LearningActivity>>;
  /** Most recently accessed resources, for "Continue learning". */
  recent(limit?: number): Promise<LearningActivity[]>;
  /** Reports viewer progress. Called periodically by the PDF viewer. */
  recordProgress(resourceId: ID, page: number, secondsSpent: number): Promise<void>;
}

export const learningApi: LearningApi = {
  history: (params) => http.get("/student/learning-history/", { params: { ...params } }),

  // Derive "recent" from the history list sorted by last-accessed.
  async recent(limit = 4) {
    const res = await http.get<PaginatedResponse<LearningActivity>>("/student/learning-history/", {
      params: { page_size: limit, sort: "-last_accessed" },
    });
    return res.data ?? [];
  },

  recordProgress: (resourceId, page, secondsSpent) =>
    http.post(`/student/viewing/resources/${resourceId}/activity/`, { page, seconds_spent: secondsSpent }),
};
