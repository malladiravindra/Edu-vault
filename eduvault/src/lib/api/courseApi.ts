/**
 * Course API — real backend endpoints.
 *
 * Admin endpoints (all under /api/admin/course/):
 *   GET    /api/admin/course/            → paginated course list
 *   GET    /api/admin/course/:id/        → course detail
 *   POST   /api/admin/course/            → create course
 *   PATCH  /api/admin/course/:id/        → update course
 *   POST   /api/admin/course/:id/publish/   → set status to published
 *   POST   /api/admin/course/:id/unpublish/ → set status to draft
 *   POST   /api/admin/course/:id/archive/   → set status to archived
 *
 * Student endpoints (under /api/student/):
 *   GET    /api/student/course/          → published catalogue
 *   GET    /api/student/course/:id/      → single course detail
 *   GET    /api/student/courses/         → student's own enrolled courses
 */
import type {
  Course,
  CourseInput,
  CourseListParams,
  CourseStatus,
  ID,
  ListParams,
  PaginatedResponse,
  StudentCourse,
  StudentCourseAccess,
} from "@/types";
import { http } from "./client";

export interface StudentCatalogParams extends ListParams {
  category?: string;
  access?: StudentCourseAccess;
}

export interface CourseApi {
  // Admin
  list(params?: CourseListParams): Promise<PaginatedResponse<Course>>;
  get(id: ID): Promise<Course>;
  create(input: CourseInput): Promise<Course>;
  update(id: ID, input: Partial<CourseInput>): Promise<Course>;
  setStatus(id: ID, status: CourseStatus): Promise<Course>;
  listCategories(): Promise<string[]>;
  // Student
  catalog(params?: StudentCatalogParams): Promise<PaginatedResponse<StudentCourse>>;
  getForStudent(id: ID): Promise<StudentCourse>;
  myCourses(): Promise<StudentCourse[]>;
}

export const courseApi: CourseApi = {
  // Admin
  list: (params) => http.get("/admin/course/", { params: { ...params } }),
  get: (id) => http.get(`/admin/course/${id}/`),
  create: (input) => http.post("/admin/course/", input),
  update: (id, input) => http.patch(`/admin/course/${id}/`, input),
  setStatus(id, status) {
    // The backend exposes separate action endpoints per status transition.
    const action = status === "published" ? "publish" : status === "archived" ? "archive" : "unpublish";
    return http.post(`/admin/course/${id}/${action}/`);
  },
  // The backend does not expose a standalone categories list endpoint.
  // Fetch the full course list and extract unique categories client-side.
  async listCategories() {
    const res = await http.get<PaginatedResponse<Course> | Course[]>("/admin/course/", { params: { page_size: 200 } });
    const items = Array.isArray(res) ? res : res.data ?? [];
    return [...new Set(items.map((c) => c.category))].sort();
  },

  // Student
  catalog: (params) => http.get("/student/course/", { params: { ...params } }),
  getForStudent: (id) => http.get(`/student/course/${id}/`),
  myCourses: () =>
    http.get<StudentCourse[] | { data?: StudentCourse[] }>("/student/courses/").then((r) => {
      if (Array.isArray(r)) return r;
      if (r && typeof r === "object" && "data" in r && Array.isArray(r.data)) return r.data;
      return [];
    }),
};
