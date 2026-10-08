/**
 * Payment API — real backend endpoints.
 *
 * Admin payments (under /api/admin/students/payments/):
 *   GET /api/admin/students/payments/          → paginated list
 *   GET /api/admin/students/payments/:id/      → detail
 *
 * Student payments (under /api/student/):
 *   GET  /api/student/payments/                        → own payment history
 *   POST /api/student/payment/create-checkout/         → create Stripe checkout session
 *
 * Note: The backend has no checkout summary endpoint. The frontend CheckoutSummary
 * is constructed from the course detail and access record client-side.
 */
import type { CheckoutSession, CheckoutSummary, ID, PaginatedResponse, Payment, PaymentListParams } from "@/types";
import { http } from "./client";

export interface PaymentApi {
  // Admin
  list(params?: PaymentListParams): Promise<PaginatedResponse<Payment>>;
  // Student
  listMine(params?: PaymentListParams): Promise<PaginatedResponse<Payment>>;
  getCheckoutSummary(courseId: ID): Promise<CheckoutSummary>;
  createCheckoutSession(courseId: ID): Promise<CheckoutSession>;
}

export const paymentApi: PaymentApi = {
  // Admin
  list: (params) => http.get("/admin/students/payments/", { params: { ...params } }),

  // Student
  listMine: (params) => http.get("/student/payments/", { params: { ...params } }),

  // The backend has no checkout summary endpoint, so we call the course detail
  // to build the summary. The student's access status for the course determines
  // the payment state.
  async getCheckoutSummary(courseId) {
    const course = await http.get<{
      id: string;
      name?: string;
      title?: string;
      price?: number;
      price_amount?: number;
      currency?: string;
      access_duration_days?: number | null;
    }>(`/student/course/${courseId}/`);
    const price = course.price ?? Math.round((course.price_amount ?? 0) * 100);
    return {
      courseId,
      courseName: course.name ?? course.title ?? "Course",
      subtotal: price,
      tax: 0,
      total: price,
      currency: course.currency ?? "USD",
      accessDurationDays: course.access_duration_days ?? null,
      paymentStatus: "not_started",
    };
  },

  async createCheckoutSession(courseId) {
    const res = await http.post<{ id: string; checkout_url: string }>("/student/payment/create-checkout/", {
      course: courseId,
    });
    return {
      sessionId: res.id,
      redirectUrl: res.checkout_url,
    };
  },
};
