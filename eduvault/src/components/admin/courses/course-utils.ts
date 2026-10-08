import { ApiError } from "@/lib/api/client";

export function isNotFoundError(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}
