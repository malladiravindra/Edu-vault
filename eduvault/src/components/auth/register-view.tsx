"use client";

import { useState } from "react";
import Link from "next/link";
import { Controller, useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Check, Circle, Lock, LockKeyhole, Mail, MailCheck, MailOpen, Phone, UserRound, KeyRound } from "lucide-react";
import { useRegister, useSendRegistrationOtp, useVerifyRegistrationOtp } from "@/hooks/use-auth";
import { getErrorMessage } from "@/lib/api/client";
import { fieldDescribedBy } from "@/components/shared/form-field";
import { cn } from "@/lib/utils";
import { PASSWORD_RULES, registerSchema, type RegisterValues } from "./auth-schemas";
import {
  HeroAlert,
  HeroButton,
  HeroCardHeader,
  HeroCheckbox,
  HeroField,
  HeroFooter,
  HeroInput,
  HeroPasswordInput,
  HeroStatus,
  heroLinkClass,
} from "./auth-hero-ui";

export function RegisterView() {
  const [step, setStep] = useState<"form" | "otp">("form");
  const [otp, setOtp] = useState("");
  const [pendingValues, setPendingValues] = useState<RegisterValues | null>(null);

  const sendOtpMutation = useSendRegistrationOtp();
  const verifyOtpMutation = useVerifyRegistrationOtp();
  const registerMutation = useRegister();

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { name: "", email: "", phone: "", password: "", confirmPassword: "", acceptTerms: false },
  });
  const password = useWatch({ control, name: "password" });

  const activeError =
    sendOtpMutation.error || verifyOtpMutation.error || registerMutation.error;

  if (registerMutation.isSuccess) {
    return (
      <HeroStatus
        icon={MailCheck}
        title="Registration Submitted"
        description={
          <>
            Your account for{" "}
            <span className="font-semibold text-white">{registerMutation.data.email}</span> has been created
            and submitted for administrator review. You will be able to sign in once approved.
          </>
        }
      >
        <Link
          href="/login"
          className="flex h-14 w-full items-center justify-center rounded-xl bg-[linear-gradient(90deg,#2563eb_0%,#3b82f6_100%)] text-lg font-semibold outline-none hover:brightness-110 focus-visible:ring-3 focus-visible:ring-[#3b82f6]/50"
        >
          Go to Sign In
        </Link>
      </HeroStatus>
    );
  }

  const onSubmitForm = (values: RegisterValues) => {
    setPendingValues(values);
    sendOtpMutation.mutate(values.email, {
      onSuccess: (data: any) => {
        if (data?.dev_otp) {
          setOtp(data.dev_otp);
        }
        setStep("otp");
      },
    });
  };

  const onVerifyAndRegister = (e: React.FormEvent) => {
    e.preventDefault();
    if (!pendingValues || !otp.trim()) return;

    if (verifyOtpMutation.isSuccess) {
      registerMutation.mutate(pendingValues);
      return;
    }

    verifyOtpMutation.mutate(
      { email: pendingValues.email, otp: otp.trim() },
      {
        onSuccess: () => {
          registerMutation.mutate(pendingValues);
        },
      },
    );
  };

  return (
    <>
      <HeroCardHeader
        title={step === "form" ? "Create" : "Verify"}
        accent={step === "form" ? "Account" : "Email"}
        description={
          step === "form"
            ? "Register to browse courses and request access"
            : `Enter the 6-digit verification code sent to ${pendingValues?.email}`
        }
      />

      {activeError && <HeroAlert message={getErrorMessage(activeError)} />}

      {step === "form" ? (
        <form
          onSubmit={handleSubmit(onSubmitForm)}
          noValidate
          className="mt-8 space-y-6 lg:mt-[clamp(14px,3vh,40px)] lg:space-y-[clamp(10px,2vh,24px)]"
        >
          <HeroField id="name" label="Full name" icon={UserRound} error={errors.name?.message}>
            <HeroInput
              id="name"
              icon={UserRound}
              autoComplete="name"
              placeholder="Your full name"
              aria-invalid={!!errors.name}
              aria-describedby={fieldDescribedBy("name", errors.name)}
              {...register("name")}
            />
          </HeroField>

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

          <HeroField id="phone" label="Phone number" icon={Phone} error={errors.phone?.message}>
            <HeroInput
              id="phone"
              icon={Phone}
              type="tel"
              autoComplete="tel"
              placeholder="+1234567890"
              aria-invalid={!!errors.phone}
              aria-describedby={fieldDescribedBy("phone", errors.phone)}
              {...register("phone")}
            />
          </HeroField>

          <div className="grid gap-6 sm:grid-cols-2 sm:gap-4 lg:gap-[clamp(10px,2vh,24px)] lg:gap-x-4">
            <HeroField id="password" label="Password" icon={Lock} error={errors.password?.message}>
              <HeroPasswordInput
                id="password"
                autoComplete="new-password"
                aria-invalid={!!errors.password}
                aria-describedby={[fieldDescribedBy("password", errors.password), "password-rules"].filter(Boolean).join(" ")}
                {...register("password")}
              />
            </HeroField>
            <HeroField id="confirmPassword" label="Confirm password" icon={LockKeyhole} error={errors.confirmPassword?.message}>
              <HeroPasswordInput
                id="confirmPassword"
                autoComplete="new-password"
                aria-invalid={!!errors.confirmPassword}
                aria-describedby={fieldDescribedBy("confirmPassword", errors.confirmPassword)}
                {...register("confirmPassword")}
              />
            </HeroField>
          </div>

          <ul id="password-rules" aria-label="Password requirements" className="flex flex-wrap gap-x-5 gap-y-1.5 text-sm">
            {PASSWORD_RULES.map((rule) => {
              const met = rule.test(password);
              return (
                <li key={rule.id} className={cn("flex items-center gap-1.5", met ? "text-emerald-300" : "text-[#8ea3cc]")}>
                  {met ? <Check className="size-4" aria-hidden /> : <Circle className="size-3" aria-hidden />}
                  {rule.label}
                  <span className="sr-only">{met ? "(met)" : "(not met)"}</span>
                </li>
              );
            })}
          </ul>

          <div className="space-y-1.5">
            <div className="flex items-start gap-3">
              <Controller
                control={control}
                name="acceptTerms"
                render={({ field }) => (
                  <HeroCheckbox
                    id="acceptTerms"
                    name={field.name}
                    checked={field.value}
                    onCheckedChange={(checked) => field.onChange(checked)}
                    inputRef={field.ref}
                    aria-invalid={!!errors.acceptTerms}
                    aria-describedby={fieldDescribedBy("acceptTerms", errors.acceptTerms)}
                  />
                )}
              />
              <label htmlFor="acceptTerms" className="text-base leading-6 text-[#e2e9f7]">
                I agree to the{" "}
                <a href="#terms" className={heroLinkClass}>
                  Terms of Service
                </a>{" "}
                and{" "}
                <a href="#privacy" className={heroLinkClass}>
                  Privacy Policy
                </a>
              </label>
            </div>
            {errors.acceptTerms && (
              <p id="acceptTerms-error" role="alert" className="text-sm text-red-300">
                {errors.acceptTerms.message}
              </p>
            )}
          </div>

          <HeroButton type="submit" pending={sendOtpMutation.isPending} pendingLabel="Sending verification code…">
            Continue to Email Verification
          </HeroButton>
        </form>
      ) : (
        <form onSubmit={onVerifyAndRegister} noValidate className="mt-8 space-y-6">
          <HeroField id="otp" label="6-Digit Verification Code" icon={KeyRound}>
            <HeroInput
              id="otp"
              icon={KeyRound}
              type="text"
              maxLength={6}
              placeholder="123456"
              autoFocus
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
            />
          </HeroField>

          <HeroButton
            type="submit"
            pending={verifyOtpMutation.isPending || registerMutation.isPending}
            pendingLabel="Verifying & Registering…"
          >
            Verify & Create Account
          </HeroButton>

          <div className="text-center pt-2">
            <button
              type="button"
              onClick={() => setStep("form")}
              className={`${heroLinkClass} text-sm`}
            >
              ← Edit Registration Details
            </button>
          </div>
        </form>
      )}

      <HeroFooter>
        Already have an account?{" "}
        <Link href="/login" className={`${heroLinkClass} ml-1 text-lg`}>
          Sign In
        </Link>
      </HeroFooter>
    </>
  );
}
