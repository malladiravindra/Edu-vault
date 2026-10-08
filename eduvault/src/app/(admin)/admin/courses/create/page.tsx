import type { Metadata } from "next";
import { CourseCreateView } from "@/components/admin/courses/course-create-view";

export const metadata: Metadata = { title: "Create course" };

export default function CreateCoursePage() {
  return <CourseCreateView />;
}
