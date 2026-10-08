import type { Metadata } from "next";
import { StudentNotificationsView } from "@/components/student/notifications/student-notifications-view";

export const metadata: Metadata = { title: "Notifications" };

export default function StudentNotificationsPage() {
  return <StudentNotificationsView />;
}
