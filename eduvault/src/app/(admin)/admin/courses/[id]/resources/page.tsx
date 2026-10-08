import type { Metadata } from "next";
import { CourseResourcesView } from "@/components/admin/resources/course-resources-view";

export const metadata: Metadata = { title: "Course resources" };

export default async function CourseResourcesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CourseResourcesView courseId={id} />;
}
