import type { Metadata } from "next";
import { StudentDetailView } from "@/components/admin/students/student-detail-view";

export const metadata: Metadata = { title: "Student" };

export default async function StudentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <StudentDetailView id={id} />;
}
