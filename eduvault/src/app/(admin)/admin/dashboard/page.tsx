import type { Metadata } from "next";
import { AdminDashboardView } from "@/components/admin/dashboard/admin-dashboard-view";

export const metadata: Metadata = { title: "Dashboard" };

export default function AdminDashboardPage() {
  return <AdminDashboardView />;
}
