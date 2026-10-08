/**
 * Notification API — real backend endpoints.
 *
 * Both portals use the same view class, differentiated only by permission class:
 *
 * Student (/api/student/notifications/):
 *   GET  /api/student/notifications/               → paginated list
 *   POST /api/student/notifications/read-all/      → mark all read
 *   GET  /api/student/notifications/:id/           → detail
 *   POST /api/student/notifications/:id/read/      → mark one read
 *
 * Admin (/api/admin/notifications/):
 *   GET  /api/admin/notifications/                 → paginated list
 *   POST /api/admin/notifications/read-all/        → mark all read
 *   GET  /api/admin/notifications/:id/             → detail
 *   POST /api/admin/notifications/:id/read/        → mark one read
 *
 * Note: There is no /unread-count/ endpoint. The frontend derives this
 * from the paginated list response by reading the `unread_count` field
 * that the backend includes in the response envelope, or by counting the
 * first page of unread notifications.
 */
import type { ID, Notification, NotificationListParams, PaginatedResponse } from "@/types";
import { http } from "./client";

/** Which portal's notification feed. The backend derives the user from the JWT. */
export type NotificationScope = "admin" | "student";

export interface NotificationApi {
  list(scope: NotificationScope, params?: NotificationListParams): Promise<PaginatedResponse<Notification>>;
  unreadCount(scope: NotificationScope): Promise<number>;
  markRead(scope: NotificationScope, id: ID): Promise<void>;
  markAllRead(scope: NotificationScope): Promise<void>;
}

export const notificationApi: NotificationApi = {
  list: (scope, params) =>
    http.get(`/${scope}/notifications/`, { params: { ...params } }),

  // Derive unread count by fetching only unread notifications and reading the total.
  async unreadCount(scope) {
    const res = await http.get<PaginatedResponse<Notification> & { unread_count?: number }>(
      `/${scope}/notifications/`,
      { params: { read: false, page_size: 1 } },
    );
    // Some backend implementations include unread_count in the envelope.
    if (typeof res.unread_count === "number") return res.unread_count;
    return res.total ?? 0;
  },

  markRead: (scope, id) => http.post(`/${scope}/notifications/${id}/read/`),
  markAllRead: (scope) => http.post(`/${scope}/notifications/read-all/`),
};
