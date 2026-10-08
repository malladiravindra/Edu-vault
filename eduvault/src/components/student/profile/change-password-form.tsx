"use client";

import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check, Circle, Loader2 } from "lucide-react";
import { ApiError } from "@/lib/api/client";
import { notify } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { useChangePassword } from "@/hooks/use-students";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { PASSWORD_REQUIREMENTS, changePasswordSchema, type ChangePasswordValues } from "./profile-schemas";

const EMPTY: ChangePasswordValues = { currentPassword: "", newPassword: "", confirmPassword: "" };
const FIELDS = Object.keys(EMPTY) as (keyof ChangePasswordValues)[];

function isField(key: string): key is keyof ChangePasswordValues {
  return (FIELDS as string[]).includes(key);
}

export function ChangePasswordForm() {
  const changePassword = useChangePassword();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    control,
    formState: { errors },
  } = useForm<ChangePasswordValues>({ resolver: zodResolver(changePasswordSchema), defaultValues: EMPTY });
  const newPassword = useWatch({ control, name: "newPassword" }) ?? "";

  const onSubmit = handleSubmit((values) => {
    changePassword.mutate(
      { currentPassword: values.currentPassword, newPassword: values.newPassword },
      {
        onSuccess: () => {
          notify.success("Password updated", "Use your new password the next time you sign in.");
          reset(EMPTY);
        },
        onError: (err) => {
          const fieldErrors = err instanceof ApiError ? err.fieldErrors : undefined;
          let mapped = false;
          if (fieldErrors) {
            for (const [key, messages] of Object.entries(fieldErrors)) {
              if (isField(key) && messages.length > 0) {
                setError(key, { type: "server", message: messages[0] }, { shouldFocus: !mapped });
                mapped = true;
              }
            }
          }
          if (!mapped) notify.error(err, "Couldn't change password");
        },
      },
    );
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      <FormField id="current-password" label="Current password" error={errors.currentPassword?.message} required>
        <Input
          id="current-password"
          type="password"
          autoComplete="current-password"
          aria-invalid={!!errors.currentPassword}
          aria-describedby={fieldDescribedBy("current-password", errors.currentPassword)}
          {...register("currentPassword")}
        />
      </FormField>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField id="new-password" label="New password" error={errors.newPassword?.message} required>
          <Input
            id="new-password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.newPassword}
            aria-describedby={cn(fieldDescribedBy("new-password", errors.newPassword), "new-password-requirements")}
            {...register("newPassword")}
          />
        </FormField>
        <FormField id="confirm-password" label="Confirm new password" error={errors.confirmPassword?.message} required>
          <Input
            id="confirm-password"
            type="password"
            autoComplete="new-password"
            aria-invalid={!!errors.confirmPassword}
            aria-describedby={fieldDescribedBy("confirm-password", errors.confirmPassword)}
            {...register("confirmPassword")}
          />
        </FormField>
      </div>
      <ul id="new-password-requirements" className="grid gap-1.5 text-xs sm:grid-cols-3" aria-label="Password requirements">
        {PASSWORD_REQUIREMENTS.map((req) => {
          const met = req.test(newPassword);
          return (
            <li key={req.label} className={cn("flex items-center gap-1.5", met ? "text-success" : "text-muted-foreground")}>
              {met ? <Check className="size-3.5" aria-hidden /> : <Circle className="size-3" aria-hidden />}
              {req.label}
              <span className="sr-only">{met ? "(met)" : "(not met)"}</span>
            </li>
          );
        })}
      </ul>
      <div className="flex justify-end">
        <Button type="submit" disabled={changePassword.isPending}>
          {changePassword.isPending && <Loader2 className="animate-spin" />}
          Update password
        </Button>
      </div>
    </form>
  );
}
