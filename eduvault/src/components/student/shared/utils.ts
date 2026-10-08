import { ApiError } from "@/lib/api/client";

export function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

export function viewerHref(courseId: string, resourceId: string, page?: number): string {
  const base = `/student/my-courses/${courseId}/resources/${resourceId}`;
  return page && page > 1 ? `${base}?page=${page}` : base;
}

/** Days-left threshold below which we warn the student about expiry. */
export const EXPIRY_WARNING_DAYS = 14;
