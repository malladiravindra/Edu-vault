import { z } from "zod";

const PHONE_PATTERN = /^\+?[0-9][0-9\s\-().]{6,19}$/;

export const profileSchema = z.object({
  name: z
    .string()
    .trim()
    .min(2, "Full name must be at least 2 characters")
    .max(80, "Full name must be 80 characters or fewer"),
  phone: z
    .string()
    .trim()
    .refine((v) => v === "" || PHONE_PATTERN.test(v), "Enter a valid phone number, e.g. +1 555 123 4567"),
});

export type ProfileValues = z.infer<typeof profileSchema>;

export const PASSWORD_MIN_LENGTH = 8;

export const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, "Enter your current password"),
    newPassword: z
      .string()
      .min(PASSWORD_MIN_LENGTH, `Use at least ${PASSWORD_MIN_LENGTH} characters`)
      .regex(/[A-Za-z]/, "Include at least one letter")
      .regex(/\d/, "Include at least one number"),
    confirmPassword: z.string().min(1, "Confirm your new password"),
  })
  .refine((v) => v.newPassword === v.confirmPassword, {
    path: ["confirmPassword"],
    message: "Passwords don't match",
  })
  .refine((v) => v.currentPassword === "" || v.newPassword !== v.currentPassword, {
    path: ["newPassword"],
    message: "Choose a password different from your current one",
  });

export type ChangePasswordValues = z.infer<typeof changePasswordSchema>;

export const PASSWORD_REQUIREMENTS: { label: string; test: (v: string) => boolean }[] = [
  { label: `At least ${PASSWORD_MIN_LENGTH} characters`, test: (v) => v.length >= PASSWORD_MIN_LENGTH },
  { label: "At least one letter", test: (v) => /[A-Za-z]/.test(v) },
  { label: "At least one number", test: (v) => /\d/.test(v) },
];
