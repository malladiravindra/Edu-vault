import type { ApiErrorBody } from "@/types";
import { API_BASE_URL } from "./config";

export class ApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly fieldErrors?: Record<string, string[]>;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.fieldErrors = body.fieldErrors;
  }
}

export type QueryValue = string | number | boolean | null | undefined;
export type QueryParams = { [key: string]: QueryValue };

interface RequestOptions {
  params?: QueryParams;
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
}

// ---------------------------------------------------------------------------
// JWT token storage (access + refresh). Persisted in localStorage so the
// session survives a page refresh. The backend issues these via /api/accounts/
// login/ and /api/admin/login/ flows.
// ---------------------------------------------------------------------------

const ACCESS_KEY = "eduvault_access";
const REFRESH_KEY = "eduvault_refresh";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

// ---------------------------------------------------------------------------
// HTTP client
// ---------------------------------------------------------------------------

function buildUrl(path: string, params?: QueryParams): string {
  const url = `${API_BASE_URL}${path}`;
  if (!params) return url;
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `${url}?${qs}` : url;
}

/** Attempt a token refresh and retry the original request once. */
async function refreshAndRetry<T>(method: string, path: string, options: RequestOptions): Promise<T> {
  const refresh = getRefreshToken();
  if (!refresh) throw new ApiError(401, { message: "Session expired. Please log in again.", code: "unauthenticated" });

  const res = await fetch(buildUrl("/accounts/refresh/"), {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ refresh }),
  });

  if (!res.ok) {
    clearTokens();
    throw new ApiError(401, { message: "Session expired. Please log in again.", code: "unauthenticated" });
  }

  const json = (await res.json()) as { data?: { tokens?: { access: string; refresh: string } }; tokens?: { access: string; refresh: string } };
  const tokens = json.data?.tokens ?? json.tokens;
  if (!tokens?.access || !tokens?.refresh) {
    clearTokens();
    throw new ApiError(401, { message: "Session expired. Please log in again.", code: "unauthenticated" });
  }
  setTokens(tokens.access, tokens.refresh);
  // Retry with the new access token
  return request<T>(method, path, options, false);
}

async function request<T>(method: string, path: string, options: RequestOptions = {}, allowRetry = true): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const accessToken = getAccessToken();

  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.body !== undefined && !isFormData ? { "Content-Type": "application/json" } : {}),
    ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    ...options.headers,
  };

  const response = await fetch(buildUrl(path, options.params), {
    method,
    headers,
    signal: options.signal,
    body:
      options.body === undefined ? undefined : isFormData ? (options.body as FormData) : JSON.stringify(options.body),
  });

  // Auto-refresh on 401 (expired token) for authenticated requests only (not login/register/refresh)
  const isAuthPath =
    path.includes("/login") ||
    path.includes("/register") ||
    path.includes("/refresh") ||
    path.includes("/forgot-password") ||
    path.includes("/reset-password");

  if (response.status === 401 && allowRetry && !isAuthPath) {
    return refreshAndRetry<T>(method, path, options);
  }

  if (!response.ok) {
    let body: ApiErrorBody = { message: response.statusText || "Request failed" };
    try {
      const json = await response.json();
      if (json && typeof json === "object") {
        if ("error" in json && json.error && typeof json.error === "object") {
          body = {
            message: json.error.message || response.statusText || "Request failed",
            code: json.error.code,
            fieldErrors: json.error.details?.fields || json.error.details,
          };
        } else if ("message" in json) {
          body = json as ApiErrorBody;
        } else if ("detail" in json) {
          body = { message: String(json.detail), code: (json as Record<string, unknown>).code as string | undefined };
        }
      }
    } catch {
      // Non-JSON error body; keep the status text.
    }
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) return undefined as T;
  const json = await response.json();

  if (json && typeof json === "object" && "success" in json) {
    // If paginated list response with meta envelope
    if (json.meta && typeof json.meta === "object" && Array.isArray(json.data)) {
      return {
        data: json.data,
        page: json.meta.page ?? 1,
        pageSize: json.meta.page_size ?? json.data.length,
        total: json.meta.count ?? json.data.length,
        totalPages: json.meta.total_pages ?? 1,
        unreadCount: json.meta.unread_count,
        ...json.meta,
      } as unknown as T;
    }
    if ("data" in json && json.data !== undefined) {
      return json.data as T;
    }
  }

  return json as T;
}

export const http = {
  get: <T>(path: string, options?: Omit<RequestOptions, "body">) => request<T>("GET", path, options),
  post: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>("POST", path, { ...options, body }),
  put: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>("PUT", path, { ...options, body }),
  patch: <T>(path: string, body?: unknown, options?: RequestOptions) => request<T>("PATCH", path, { ...options, body }),
  delete: <T>(path: string, options?: RequestOptions) => request<T>("DELETE", path, options),
};

/**
 * Upload with progress reporting. `fetch` has no upload progress events,
 * so this uses XMLHttpRequest.
 */
export function uploadWithProgress<T>(
  path: string,
  formData: FormData,
  onProgress?: (percent: number) => void,
  method: "POST" | "PUT" = "POST",
): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open(method, buildUrl(path));
    xhr.setRequestHeader("Accept", "application/json");
    const token = getAccessToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let parsed: unknown;
      try {
        parsed = xhr.responseText ? JSON.parse(xhr.responseText) : undefined;
      } catch {
        parsed = undefined;
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(parsed as T);
      else reject(new ApiError(xhr.status, (parsed as ApiErrorBody) ?? { message: "Upload failed" }));
    };
    xhr.onerror = () => reject(new ApiError(0, { message: "Network error during upload" }));
    xhr.send(formData);
  });
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
}
