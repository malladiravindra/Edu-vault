import type { Metadata } from "next";
import { StudentDashboardView } from "@/components/student/dashboard/student-dashboard-view";

export const metadata: Metadata = { title: "Dashboard" };

export default function StudentDashboardPage() {
  return <StudentDashboardView />;
}
