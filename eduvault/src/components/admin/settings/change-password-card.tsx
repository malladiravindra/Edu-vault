"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { notify } from "@/lib/toast";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { Input } from "@/components/ui/input";
import { changePasswordSchema, type ChangePasswordValues } from "./settings-schema";
import { SettingsCard } from "./settings-card";

const EMPTY: ChangePasswordValues = { currentPassword: "", newPassword: "", confirmPassword: "" };
const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function ChangePasswordCard() {
  const form = useForm<ChangePasswordValues>({ resolver: zodResolver(changePasswordSchema), defaultValues: EMPTY });
  const {
    register,
    formState: { errors, isDirty, isSubmitting },
  } = form;

  const onSubmit = form.handleSubmit(async () => {
    // UI-only: no password endpoint is wired for admins yet.
    await wait(700);
    form.reset(EMPTY);
    notify.success("Password updated", "Use your new password the next time you sign in.");
  });

  return (
    <SettingsCard
      id="change-password"
      title="Change password"
      description="Use at least 8 characters with a mix of letters and numbers."
      onSubmit={onSubmit}
      onDiscard={() => form.reset(EMPTY)}
      isDirty={isDirty}
      isPending={isSubmitting}
      submitLabel="Update password"
    >
      <div className="grid gap-4 sm:max-w-md">
        <FormField id="currentPassword" label="Current password" error={errors.currentPassword?.message} required>
          <Input
            id="currentPassword"
            type="password"
            autoComplete="current-password"
            aria-invalid={!!errors.currentPassword}
            aria-describedby={fieldDescribedBy("currentPassword", errors.currentPassword)}
            {...register("currentPassword")}
          />
        </FormField>
        <FormField id="newPassword" label="New password" error={errors.newPassword?.message} required>
          <Input
            id="newPassword"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.newPassword}
            aria-describedby={fieldDescribedBy("newPassword", errors.newPassword)}
            {...register("newPassword")}
          />
        </FormField>
        <FormField id="confirmPassword" label="Confirm new password" error={errors.confirmPassword?.message} required>
          <Input
            id="confirmPassword"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.confirmPassword}
            aria-describedby={fieldDescribedBy("confirmPassword", errors.confirmPassword)}
            {...register("confirmPassword")}
          />
        </FormField>
      </div>
    </SettingsCard>
  );
}
