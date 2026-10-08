/**
 * Resource API — real backend endpoints.
 *
 * Admin resource management (under /api/admin/course/resources/):
 *   GET    /api/admin/course/resources/                     → list all resources
 *   POST   /api/admin/course/resources/                     → upload (multipart)
 *   GET    /api/admin/course/resources/:id/                 → resource detail
 *   PATCH  /api/admin/course/resources/:id/replace/         → replace file (multipart PUT)
 *   POST   /api/admin/course/resources/:id/publish/         → set status to published
 *   POST   /api/admin/course/resources/:id/archive/         → set status to archived/draft
 *
 * Student viewer (under /api/student/viewing/):
 *   GET    /api/student/viewing/courses/:courseId/resources/ → list published resources for course
 *   GET    /api/student/viewing/resources/:id/              → open viewer session (returns metadata)
 *   GET    /api/student/viewing/resources/:id/pages/:page/  → get a rendered page image
 *   POST   /api/student/viewing/resources/:id/activity/     → record progress
 */
import type { ID, PaginatedResponse, Resource, ResourcePage, ResourceStatus, ResourceViewerSession } from "@/types";
import { http, uploadWithProgress } from "./client";

export interface ResourceUploadInput {
  file: File;
  name: string;
  description?: string;
  publish: boolean;
}

export interface ResourceApi {
  // Admin
  listByCourse(courseId: ID): Promise<Resource[]>;
  upload(courseId: ID, input: ResourceUploadInput, onProgress?: (percent: number) => void): Promise<Resource>;
  replace(id: ID, file: File, onProgress?: (percent: number) => void): Promise<Resource>;
  setStatus(id: ID, status: Exclude<ResourceStatus, "processing">): Promise<Resource>;
  remove(id: ID): Promise<void>;
  // Student
  listPublishedByCourse(courseId: ID): Promise<Resource[]>;
  openViewerSession(resourceId: ID, mode?: "student" | "admin-preview"): Promise<ResourceViewerSession>;
  getPage(resourceId: ID, pageNumber: number): Promise<ResourcePage>;
}

function toForm(fields: Record<string, string | Blob>): FormData {
  const form = new FormData();
  for (const [k, v] of Object.entries(fields)) form.append(k, v);
  return form;
}

function mapResource(raw: Record<string, unknown>): Resource {
  return {
    id: String(raw.id ?? ""),
    courseId: String(raw.course ?? raw.courseId ?? ""),
    name: String(raw.title ?? raw.name ?? ""),
    description: (raw.description as string) || undefined,
    type: "pdf",
    status: (raw.status as ResourceStatus) || "draft",
    pageCount: Number(raw.page_count ?? raw.pageCount ?? 0),
    fileSizeBytes: Number(raw.file_size ?? raw.fileSizeBytes ?? 0),
    order: Number(raw.order ?? 0),
    createdAt: String(raw.created_at ?? raw.createdAt ?? ""),
    updatedAt: String(raw.updated_at ?? raw.updatedAt ?? ""),
  };
}

export const resourceApi: ResourceApi = {
  // Admin
  async listByCourse(courseId) {
    const res = await http.get<PaginatedResponse<Record<string, unknown>> | Record<string, unknown>[]>(
      "/admin/course/resources/",
      { params: { course: courseId, page_size: 100 } },
    );
    const items = Array.isArray(res) ? res : res?.data ?? [];
    return items.map(mapResource);
  },

  async upload(courseId, input, onProgress) {
    const raw = await uploadWithProgress<Record<string, unknown>>(
      "/admin/course/resources/",
      toForm({
        file: input.file,
        title: input.name,
        description: input.description ?? "",
        course: courseId,
      }),
      onProgress,
    );
    return mapResource(raw);
  },

  async replace(id, file, onProgress) {
    const raw = await uploadWithProgress<Record<string, unknown>>(
      `/admin/course/resources/${id}/replace/`,
      toForm({ file }),
      onProgress,
      "PUT",
    );
    return mapResource(raw);
  },

  async setStatus(id, status) {
    const action = status === "published" ? "publish" : "archive";
    const raw = await http.post<Record<string, unknown>>(`/admin/course/resources/${id}/${action}/`);
    return mapResource(raw);
  },

  remove: (id) => http.delete(`/admin/course/resources/${id}/`),

  // Student
  async listPublishedByCourse(courseId) {
    const res = await http.get<PaginatedResponse<Record<string, unknown>> | Record<string, unknown>[]>(
      `/student/viewing/courses/${courseId}/resources/`,
    );
    const items = Array.isArray(res) ? res : res?.data ?? [];
    return items.map(mapResource);
  },

  async openViewerSession(resourceId, mode = "student") {
    const raw = await http.get<Record<string, unknown>>(
      mode === "admin-preview"
        ? `/admin/course/resources/${resourceId}/`
        : `/student/viewing/resources/${resourceId}/`,
    );
    return {
      resourceId: String(raw.id ?? resourceId),
      courseId: String(raw.course ?? ""),
      resourceName: String(raw.title ?? raw.resourceName ?? ""),
      courseName: String(raw.course_title ?? raw.courseName ?? ""),
      pageCount: Number(raw.page_count ?? raw.pageCount ?? 1),
      watermark: {
        name: "",
        email: "",
        label: "EduVault Protected Resource",
      },
      expiresAt: "",
    };
  },

  async getPage(resourceId, pageNumber) {
    const raw = await http.get<{
      resource?: string;
      page?: number;
      image?: string;
      content_type?: string;
      width?: number;
      height?: number;
      view_id?: string;
    }>(`/student/viewing/resources/${resourceId}/pages/${pageNumber}/`);

    const imageSrc = raw?.image ? `data:${raw.content_type || "image/jpeg"};base64,${raw.image}` : null;
    return {
      resourceId: raw?.resource ?? resourceId,
      pageNumber: raw?.page ?? pageNumber,
      imageSrc,
      width: raw?.width ?? 800,
      height: raw?.height ?? 1100,
    };
  },
};
