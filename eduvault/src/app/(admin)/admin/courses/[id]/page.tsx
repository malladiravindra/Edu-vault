import type { Metadata } from "next";
import { CourseDetailView } from "@/components/admin/courses/course-detail-view";

export const metadata: Metadata = { title: "Course" };

export default async function CourseDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CourseDetailView id={id} />;
}
