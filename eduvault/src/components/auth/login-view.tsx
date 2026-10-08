"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Lock, Mail, MailOpen, Shield, GraduationCap } from "lucide-react";
import { useAdminLogin, useStudentLogin } from "@/hooks/use-auth";
import { getErrorMessage } from "@/lib/api/client";
import { fieldDescribedBy } from "@/components/shared/form-field";
import { loginSchema, type LoginValues } from "./auth-schemas";
import { portalForChallenge } from "./auth-shared";
import {
  HeroAlert,
  HeroButton,
  HeroCardHeader,
  HeroCheckbox,
  HeroField,
  HeroFooter,
  HeroInput,
  HeroPasswordInput,
  heroLinkClass,
} from "./auth-hero-ui";

interface LoginViewProps {
  initialRole?: "student" | "admin";
}

export function LoginView({ initialRole = "student" }: LoginViewProps) {
  const router = useRouter();
  const [role, setRole] = useState<"student" | "admin">(initialRole);

  const studentLogin = useStudentLogin();
  const adminLogin = useAdminLogin();

  const activeMutation = role === "admin" ? adminLogin : studentLogin;

  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "", rememberMe: true },
  });

  const onSubmit = (values: LoginValues) => {
    activeMutation.mutate(values, {
      onSuccess: (res) => {
        if (res.requiresTwoFactor && res.challengeId) {
          const params = new URLSearchParams({
            challenge: res.challengeId,
            next: portalForChallenge(res.challengeId),
          });
          router.push(`/verify-2fa?${params.toString()}`);
          return;
        }
        router.replace(res.user?.role === "admin" ? "/admin/dashboard" : "/student/dashboard");
      },
    });
  };

  return (
    <>
      {/* Role selector tab */}
      <div className="flex rounded-2xl bg-white/5 p-1 mb-6 border border-white/10" role="tablist">
        <button
          type="button"
          role="tab"
          aria-selected={role === "student"}
          onClick={() => setRole("student")}
          className={`flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold transition-all ${
            role === "student"
              ? "bg-[linear-gradient(90deg,#2563eb_0%,#3b82f6_100%)] text-white shadow-md"
              : "text-[#94a3b8] hover:text-white"
          }`}
        >
          <GraduationCap className="size-4" />
          Student Login
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={role === "admin"}
          onClick={() => setRole("admin")}
          className={`flex-1 flex items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold transition-all ${
            role === "admin"
              ? "bg-[linear-gradient(90deg,#2563eb_0%,#3b82f6_100%)] text-white shadow-md"
              : "text-[#94a3b8] hover:text-white"
          }`}
        >
          <Shield className="size-4" />
          Admin Login
        </button>
      </div>

      <HeroCardHeader
        title={role === "admin" ? "Admin" : "Student"}
        accent="Login"
        description={
          role === "admin"
            ? "Sign in to manage the EduVault platform (requires 2FA code)"
            : "Sign in to continue to your courses and resources"
        }
      />

      {activeMutation.isError && <HeroAlert message={getErrorMessage(activeMutation.error)} />}

      <form
        onSubmit={handleSubmit(onSubmit)}
        noValidate
        className="mt-8 space-y-8 lg:space-y-[clamp(12px,2.6vh,32px)]"
      >
        <HeroField id="email" label="Email address" icon={MailOpen} error={errors.email?.message}>
          <HeroInput
            id="email"
            icon={Mail}
            type="email"
            autoComplete="email"
            placeholder={role === "admin" ? "admin@eduvault.local" : "student@example.com"}
            aria-invalid={!!errors.email}
            aria-describedby={fieldDescribedBy("email", errors.email)}
            {...register("email")}
          />
        </HeroField>

        <HeroField id="password" label="Password" icon={Lock} error={errors.password?.message}>
          <HeroPasswordInput
            id="password"
            autoComplete="current-password"
            aria-invalid={!!errors.password}
            aria-describedby={fieldDescribedBy("password", errors.password)}
            {...register("password")}
          />
        </HeroField>

        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <Controller
              control={control}
              name="rememberMe"
              render={({ field }) => (
                <HeroCheckbox
                  id="rememberMe"
                  name={field.name}
                  checked={field.value}
                  onCheckedChange={(checked) => field.onChange(checked)}
                  onBlur={field.onBlur}
                  inputRef={field.ref}
                />
              )}
            />
            <label htmlFor="rememberMe" className="text-base text-[#e2e9f7]">
              Remember me
            </label>
          </div>
          <Link href="/forgot-password" className={`${heroLinkClass} text-base`}>
            Forgot password?
          </Link>
        </div>

        <HeroButton type="submit" pending={activeMutation.isPending} pendingLabel={role === "admin" ? "Sending code…" : "Signing in…"}>
          {role === "admin" ? "Continue with OTP" : "Sign In"}
        </HeroButton>
      </form>

      {role === "student" && (
        <HeroFooter>
          Don&apos;t have an account?{" "}
          <Link href="/register" className={`${heroLinkClass} ml-1 text-lg`}>
            Sign Up
          </Link>
        </HeroFooter>
      )}

      {role === "admin" && (
        <HeroFooter>
          Looking for Django Admin?{" "}
          <a href="http://127.0.0.1:8000/admin/" className={`${heroLinkClass} ml-1 text-base`}>
            Go to /admin/
          </a>
        </HeroFooter>
      )}
    </>
  );
}
