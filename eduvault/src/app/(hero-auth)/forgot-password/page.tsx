import type { Metadata } from "next";
import { ForgotPasswordView } from "@/components/auth/forgot-password-view";

export const metadata: Metadata = { title: "Forgot password" };

export default function ForgotPasswordPage() {
  return <ForgotPasswordView />;
}
