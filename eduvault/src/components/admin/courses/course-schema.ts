import { z } from "zod";
import type { AccessModel, Course, CourseInput } from "@/types";

export const SHORT_DESCRIPTION_MAX = 160;
export const LIFETIME = "lifetime";

export const DURATION_PRESETS = [30, 90, 180, 365] as const;

export const courseSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(3, "Course name must be at least 3 characters")
      .max(120, "Keep the course name under 120 characters"),
    shortDescription: z
      .string()
      .trim()
      .min(10, "Add a short summary of at least 10 characters")
      .max(SHORT_DESCRIPTION_MAX, `Keep the short description under ${SHORT_DESCRIPTION_MAX} characters`),
    description: z
      .string()
      .trim()
      .min(20, "Describe the course in at least 20 characters")
      .max(5000, "Keep the description under 5,000 characters"),
    category: z.string().min(1, "Choose a category"),
    accessModel: z.enum(["free", "paid", "approval"], { error: "Choose an access model" }),
    /** Price in dollars, as typed by the admin. Converted to cents on submit. */
    price: z
      .number({ error: "Enter a price" })
      .min(0, "Price can't be negative")
      .max(100_000, "Price must be $100,000 or less"),
    /** Day count as a string, or "lifetime". */
    accessDuration: z.string().min(1, "Choose an access duration"),
    status: z.enum(["draft", "published", "archived"], { error: "Choose a status" }),
  })
  .superRefine((values, ctx) => {
    if (values.accessModel === "paid" && !(values.price > 0)) {
      ctx.addIssue({ code: "custom", path: ["price"], message: "Paid courses need a price above $0" });
    }
    // Reject more than two decimals (e.g. 9.999) while tolerating float noise.
    if (values.accessModel !== "free" && Math.abs(Math.round(values.price * 100) - values.price * 100) > 1e-6) {
      ctx.addIssue({ code: "custom", path: ["price"], message: "Use at most two decimal places" });
    }
    if (values.accessDuration !== LIFETIME) {
      const days = Number(values.accessDuration);
      if (!Number.isInteger(days) || days <= 0) {
        ctx.addIssue({ code: "custom", path: ["accessDuration"], message: "Choose an access duration" });
      }
    }
  });

export type CourseFormValues = z.infer<typeof courseSchema>;

export const EMPTY_COURSE_VALUES: CourseFormValues = {
  name: "",
  shortDescription: "",
  description: "",
  category: "",
  accessModel: "paid",
  price: 0,
  accessDuration: "365",
  status: "draft",
};

export function courseToFormValues(course: Course): CourseFormValues {
  return {
    name: course.name,
    shortDescription: course.shortDescription,
    description: course.description,
    category: course.category,
    accessModel: course.accessModel,
    price: course.price / 100,
    accessDuration: course.accessDurationDays === null ? LIFETIME : String(course.accessDurationDays),
    status: course.status,
  };
}

export function parseDuration(value: string): number | null {
  return value === LIFETIME ? null : Number(value);
}

export function formValuesToInput(values: CourseFormValues): CourseInput {
  return {
    name: values.name.trim(),
    shortDescription: values.shortDescription.trim(),
    description: values.description.trim(),
    category: values.category,
    accessModel: values.accessModel,
    price: values.accessModel === "free" ? 0 : Math.round(values.price * 100),
    accessDurationDays: parseDuration(values.accessDuration),
    status: values.status,
  };
}

export const ACCESS_MODEL_SHORT: Record<AccessModel, string> = {
  free: "Free",
  paid: "Paid",
  approval: "Approval",
};
