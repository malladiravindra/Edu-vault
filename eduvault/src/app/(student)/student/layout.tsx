import type { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { RoleGate } from "@/components/layout/role-gate";

export const metadata: Metadata = {
  title: { default: "Student", template: "%s · EduVault" },
};

export default function StudentLayout({ children }: LayoutProps<"/student">) {
  return (
    <RoleGate role="student">
      <AppShell role="student">{children}</AppShell>
    </RoleGate>
  );
}
