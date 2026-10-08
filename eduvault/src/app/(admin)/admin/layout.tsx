import type { Metadata } from "next";
import { AppShell } from "@/components/layout/app-shell";
import { RoleGate } from "@/components/layout/role-gate";

export const metadata: Metadata = {
  title: { default: "Admin", template: "%s · EduVault Admin" },
};

export default function AdminLayout({ children }: LayoutProps<"/admin">) {
  return (
    <RoleGate role="admin">
      <AppShell role="admin">{children}</AppShell>
    </RoleGate>
  );
}
