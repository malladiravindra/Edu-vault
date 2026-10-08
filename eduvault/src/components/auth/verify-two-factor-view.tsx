"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { REGEXP_ONLY_DIGITS } from "input-otp";
import { ArrowLeft, Loader2, ShieldAlert } from "lucide-react";
import { useResendTwoFactor, useVerifyTwoFactor } from "@/hooks/use-auth";
import { getErrorMessage } from "@/lib/api/client";
import { notify } from "@/lib/toast";
import { Button } from "@/components/ui/button";
import { InputOTP, InputOTPGroup, InputOTPSeparator, InputOTPSlot } from "@/components/ui/input-otp";
import { Label } from "@/components/ui/label";
import { AuthHeader, AuthStatus, safeNextPath } from "./auth-shared";

const CODE_LENGTH = 6;
const RESEND_COOLDOWN_S = 30;

export function VerifyTwoFactorView() {
  const searchParams = useSearchParams();
  const challengeId = searchParams.get("challenge");
  const next = safeNextPath(searchParams.get("next"));
  const router = useRouter();
  const verify = useVerifyTwoFactor();
  const resend = useResendTwoFactor();
  const [code, setCode] = useState("");
  // A code was just sent by the login step, so start in cooldown.
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_S);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = window.setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => window.clearTimeout(t);
  }, [cooldown]);

  if (!challengeId) {
    return (
      <AuthStatus
        icon={ShieldAlert}
        tone="destructive"
        title="Verification session not found"
        description="Your sign-in session is missing or has expired. Please log in again to receive a new code."
      >
        <Button nativeButton={false} render={<Link href="/login" />} className="w-full">
          Back to login
        </Button>
      </AuthStatus>
    );
  }

  const submit = (value: string) => {
    if (value.length !== CODE_LENGTH || verify.isPending) return;
    verify.mutate(
      { challengeId, code: value },
      {
        onSuccess: () => router.replace(next),
        onError: () => setCode(""),
      },
    );
  };

  const onResend = () => {
    resend.mutate(challengeId, {
      onSuccess: () => {
        setCooldown(RESEND_COOLDOWN_S);
        notify.success("A new code is on its way");
      },
      onError: (err) => notify.error(err, "Couldn't resend code"),
    });
  };

  const invalid = verify.isError;

  return (
    <div>
      <AuthHeader
        title="Admin Two-Step Verification"
        description="Enter the 6-digit code sent to your registered admin email address (valid for 5 minutes)."
      />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(code);
        }}
        className="space-y-6"
      >
        <div className="space-y-2">
          <Label htmlFor="otp">Verification code</Label>
          <InputOTP
            id="otp"
            maxLength={CODE_LENGTH}
            pattern={REGEXP_ONLY_DIGITS}
            inputMode="numeric"
            autoComplete="one-time-code"
            autoFocus
            value={code}
            disabled={verify.isPending}
            aria-invalid={invalid}
            aria-describedby={invalid ? "otp-error" : undefined}
            onChange={(value) => {
              setCode(value);
              if (verify.isError) verify.reset();
            }}
            onComplete={submit}
          >
            <InputOTPGroup>
              {[0, 1, 2].map((i) => (
                <InputOTPSlot key={i} index={i} aria-invalid={invalid} className="size-11 text-lg" />
              ))}
            </InputOTPGroup>
            <InputOTPSeparator />
            <InputOTPGroup>
              {[3, 4, 5].map((i) => (
                <InputOTPSlot key={i} index={i} aria-invalid={invalid} className="size-11 text-lg" />
              ))}
            </InputOTPGroup>
          </InputOTP>
          {invalid && (
            <p id="otp-error" role="alert" className="text-xs font-medium text-destructive">
              {getErrorMessage(verify.error)}
            </p>
          )}
        </div>

        <Button type="submit" className="w-full" size="lg" disabled={verify.isPending || code.length !== CODE_LENGTH}>
          {verify.isPending && <Loader2 className="animate-spin" aria-hidden />}
          {verify.isPending ? "Verifying…" : "Verify"}
        </Button>
      </form>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-2 text-sm">
        <Link
          href="/login"
          className="inline-flex items-center gap-1 font-medium text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" aria-hidden />
          Back to login
        </Link>
        <Button
          type="button"
          variant="link"
          size="sm"
          className="px-0"
          onClick={onResend}
          disabled={cooldown > 0 || resend.isPending}
        >
          {resend.isPending && <Loader2 className="animate-spin" aria-hidden />}
          {cooldown > 0 ? (
            <span className="tabular-nums">Resend code in {cooldown}s</span>
          ) : (
            "Resend code"
          )}
        </Button>
      </div>
    </div>
  );
}
