import type { Metadata } from "next";
import { RegisterView } from "@/components/auth/register-view";

export const metadata: Metadata = { title: "Register" };

export default function RegisterPage() {
  return <RegisterView />;
}
