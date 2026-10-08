import type { Metadata } from "next";
import { CourseLearningView } from "@/components/student/my-courses/course-learning-view";

export const metadata: Metadata = { title: "Course" };

export default async function CourseLearningPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CourseLearningView id={id} />;
}
