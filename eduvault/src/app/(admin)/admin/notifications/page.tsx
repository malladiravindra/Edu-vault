import type { Metadata } from "next";
import { AdminNotificationsView } from "@/components/admin/notifications/notifications-view";

export const metadata: Metadata = { title: "Notifications" };

export default function AdminNotificationsPage() {
  return <AdminNotificationsView />;
}
