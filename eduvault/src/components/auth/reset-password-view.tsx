"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2, Link2Off, Loader2 } from "lucide-react";
import { useResetPassword } from "@/hooks/use-auth";
import { getErrorMessage } from "@/lib/api/client";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { resetPasswordSchema, type ResetPasswordValues } from "./auth-schemas";
import { AuthErrorAlert, AuthHeader, AuthStatus, PasswordChecklist, PasswordInput } from "./auth-shared";

export function ResetPasswordView() {
  const token = useSearchParams().get("token");
  const reset = useResetPassword();
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { password: "", confirmPassword: "" },
  });
  const password = useWatch({ control, name: "password" });

  if (!token) {
    return (
      <AuthStatus
        icon={Link2Off}
        tone="destructive"
        title="Invalid or expired link"
        description="This password reset link is no longer valid. Request a new one to continue."
      >
        <Button nativeButton={false} render={<Link href="/forgot-password" />} className="w-full">
          Request a new link
        </Button>
      </AuthStatus>
    );
  }

  if (reset.isSuccess) {
    return (
      <AuthStatus
        icon={CheckCircle2}
        title="Password updated"
        description="Your password has been reset. You can now log in with your new password."
      >
        <Button nativeButton={false} render={<Link href="/login" />} className="w-full">
          Continue to login
        </Button>
      </AuthStatus>
    );
  }

  return (
    <div>
      <AuthHeader title="Set a new password" description="Choose a strong password you haven't used before." />

      {reset.isError && <AuthErrorAlert message={getErrorMessage(reset.error)} />}

      <form
        onSubmit={handleSubmit(({ password }) => reset.mutate({ token, password }))}
        noValidate
        className="space-y-5"
      >
        <FormField id="password" label="New password" error={errors.password?.message} required>
          <PasswordInput
            id="password"
            autoComplete="new-password"
            aria-invalid={!!errors.password}
            aria-describedby={[fieldDescribedBy("password", errors.password), "password-rules"].filter(Boolean).join(" ")}
            {...register("password")}
          />
          <PasswordChecklist id="password-rules" value={password} />
        </FormField>

        <FormField id="confirmPassword" label="Confirm new password" error={errors.confirmPassword?.message} required>
          <PasswordInput
            id="confirmPassword"
            autoComplete="new-password"
            aria-invalid={!!errors.confirmPassword}
            aria-describedby={fieldDescribedBy("confirmPassword", errors.confirmPassword)}
            {...register("confirmPassword")}
          />
        </FormField>

        <Button type="submit" className="w-full" size="lg" disabled={reset.isPending}>
          {reset.isPending && <Loader2 className="animate-spin" aria-hidden />}
          {reset.isPending ? "Updating password…" : "Reset password"}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Remembered it?{" "}
        <Link href="/login" className="font-medium text-primary hover:underline">
          Back to login
        </Link>
      </p>
    </div>
  );
}
