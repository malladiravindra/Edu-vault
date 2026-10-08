import type { Metadata } from "next";
import { CourseDetailsView } from "@/components/student/courses/course-details-view";

export const metadata: Metadata = { title: "Course Details" };

export default async function CourseDetailsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CourseDetailsView id={id} />;
}
