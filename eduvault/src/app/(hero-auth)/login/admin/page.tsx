import type { Metadata } from "next";
import { LoginView } from "@/components/auth/login-view";

export const metadata: Metadata = { title: "Admin Log in" };

export default function AdminLoginPage() {
  return <LoginView initialRole="admin" />;
}
