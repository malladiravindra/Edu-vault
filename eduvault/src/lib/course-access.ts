import type { ID, StudentCourseAccess } from "@/types";

export type CourseCtaKind = "request" | "status" | "pay" | "open" | "expired" | "suspended";

export interface CourseCta {
  kind: CourseCtaKind;
  /** Label on course cards. */
  cardLabel: string;
  /** Label on the course details page. */
  detailLabel: string;
  href?: string;
  disabled?: boolean;
  variant: "default" | "outline" | "secondary";
}

/**
 * Single source of truth for what a student can do with a course in a given
 * access state. Used by CourseCard and the course details page.
 */
export function getCourseCta(courseId: ID, access: StudentCourseAccess): CourseCta {
  switch (access) {
    case "pending":
      return { kind: "status", cardLabel: "View Status", detailLabel: "Awaiting Approval", href: `/student/courses/${courseId}`, variant: "outline" };
    case "payment_required":
      return {
        kind: "pay",
        cardLabel: "Proceed to Payment",
        detailLabel: "Proceed to Payment",
        href: `/student/payments/checkout?course=${courseId}`,
        variant: "default",
      };
    case "active":
      return { kind: "open", cardLabel: "Open Course", detailLabel: "Start Learning", href: `/student/my-courses/${courseId}`, variant: "default" };
    case "expired":
      return { kind: "expired", cardLabel: "Access Expired", detailLabel: "Access Expired", disabled: true, variant: "secondary" };
    case "suspended":
      return { kind: "suspended", cardLabel: "Access Suspended", detailLabel: "Access Suspended", disabled: true, variant: "secondary" };
    case "none":
    default:
      return { kind: "request", cardLabel: "Request Access", detailLabel: "Request Access", variant: "default" };
  }
}
