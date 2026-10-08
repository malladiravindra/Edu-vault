import type { Metadata } from "next";
import { Suspense } from "react";
import { VerifyTwoFactorView } from "@/components/auth/verify-two-factor-view";

export const metadata: Metadata = { title: "Two-step verification" };

export default function VerifyTwoFactorPage() {
  return (
    <Suspense>
      <VerifyTwoFactorView />
    </Suspense>
  );
}
