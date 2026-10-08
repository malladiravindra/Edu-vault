import { z } from "zod";

const intInRange = (label: string, min: number, max: number) =>
  z
    .number({ error: `Enter ${label}` })
    .int(`${label[0].toUpperCase()}${label.slice(1)} must be a whole number`)
    .min(min, `Must be at least ${min}`)
    .max(max, `Must be ${max} or less`);

export const profileSchema = z.object({
  name: z.string().trim().min(2, "Enter your full name").max(80, "Keep it under 80 characters"),
  title: z.string().trim().max(80, "Keep it under 80 characters"),
});
export type ProfileValues = z.infer<typeof profileSchema>;

export const platformSchema = z.object({
  platformName: z.string().trim().min(2, "Enter a platform name").max(60, "Keep it under 60 characters"),
  supportEmail: z.email("Enter a valid email"),
  defaultCurrency: z.string().min(1, "Choose a currency"),
  timezone: z.string().min(1, "Choose a timezone"),
  allowSelfRegistration: z.boolean(),
  maintenanceMode: z.boolean(),
});
export type PlatformValues = z.infer<typeof platformSchema>;

export const notificationsSchema = z.object({
  emailNewRegistration: z.boolean(),
  emailPaymentReceived: z.boolean(),
  emailAccessExpiring: z.boolean(),
  inAppSystemAlerts: z.boolean(),
  weeklyDigest: z.boolean(),
});
export type NotificationsValues = z.infer<typeof notificationsSchema>;

export const accessDefaultsSchema = z.object({
  defaultAccessModel: z.enum(["free", "paid", "approval"]),
  defaultAccessDurationDays: z.number().int().positive().nullable(),
  autoApproveFreeCourses: z.boolean(),
  expiryReminderDays: intInRange("a number of days", 1, 60),
});
export type AccessDefaultsValues = z.infer<typeof accessDefaultsSchema>;

export const securitySchema = z.object({
  requireTwoFactorForAdmins: z.boolean(),
  sessionTimeoutMinutes: z.number().int().positive(),
  maxLoginAttempts: intInRange("a number of attempts", 3, 10),
  watermarkEnabled: z.boolean(),
});
export type SecurityValues = z.infer<typeof securitySchema>;

export const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, "Enter your current password"),
    newPassword: z
      .string()
      .min(8, "Use at least 8 characters")
      .regex(/[A-Za-z]/, "Include at least one letter")
      .regex(/[0-9]/, "Include at least one number"),
    confirmPassword: z.string().min(1, "Confirm your new password"),
  })
  .refine((v) => v.newPassword === v.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords don't match",
  })
  .refine((v) => v.newPassword !== v.currentPassword, {
    path: ["newPassword"],
    message: "New password must be different from the current one",
  });
export type ChangePasswordValues = z.infer<typeof changePasswordSchema>;
