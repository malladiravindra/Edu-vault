"use client";

import Link from "next/link";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Mail, MailCheck, MailOpen } from "lucide-react";
import { useForgotPassword } from "@/hooks/use-auth";
import { getErrorMessage } from "@/lib/api/client";
import { fieldDescribedBy } from "@/components/shared/form-field";
import { forgotPasswordSchema, type ForgotPasswordValues } from "./auth-schemas";
import { HeroAlert, HeroButton, HeroCardHeader, HeroField, HeroFooter, HeroInput, HeroStatus, heroLinkClass } from "./auth-hero-ui";

function BackToSignIn() {
  return (
    <HeroFooter>
      <Link href="/login" className={`${heroLinkClass} inline-flex items-center gap-2 text-lg`}>
        <ArrowLeft className="size-5" aria-hidden />
        Back to Sign In
      </Link>
    </HeroFooter>
  );
}

export function ForgotPasswordView() {
  const forgot = useForgotPassword();
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<ForgotPasswordValues>({
    resolver: zodResolver(forgotPasswordSchema),
    defaultValues: { email: "" },
  });

  if (forgot.isSuccess) {
    return (
      <>
        <HeroStatus
          icon={MailCheck}
          title="Check your email"
          description={
            <>
              If an account exists for <span className="font-semibold text-white">{forgot.variables}</span>, you&apos;ll
              receive a link to reset your password shortly.
            </>
          }
        >
          <HeroButton type="button" variant="outline" onClick={() => forgot.reset()}>
            Use a different email
          </HeroButton>
        </HeroStatus>
        <BackToSignIn />
      </>
    );
  }

  return (
    <>
      <HeroCardHeader
        title="Forgot"
        accent="Password?"
        description="Enter the email you registered with and we'll send you a reset link"
      />

      {forgot.isError && <HeroAlert message={getErrorMessage(forgot.error)} />}

      <form
        onSubmit={handleSubmit(({ email }) => forgot.mutate(email))}
        noValidate
        className="mt-12 space-y-8 lg:mt-[clamp(16px,4vh,48px)] lg:space-y-[clamp(14px,3vh,32px)]"
      >
        <HeroField id="email" label="Email address" icon={MailOpen} error={errors.email?.message}>
          <HeroInput
            id="email"
            icon={Mail}
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            aria-invalid={!!errors.email}
            aria-describedby={fieldDescribedBy("email", errors.email)}
            {...register("email")}
          />
        </HeroField>

        <HeroButton type="submit" pending={forgot.isPending} pendingLabel="Sending link…">
          Send Reset Link
        </HeroButton>
      </form>

      <BackToSignIn />
    </>
  );
}
