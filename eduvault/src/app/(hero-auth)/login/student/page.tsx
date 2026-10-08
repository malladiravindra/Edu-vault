import type { Metadata } from "next";
import { LoginView } from "@/components/auth/login-view";

export const metadata: Metadata = { title: "Student Log in" };

export default function StudentLoginPage() {
  return <LoginView initialRole="student" />;
}
