import type { Metadata } from "next";
import { CourseCatalogView } from "@/components/student/courses/course-catalog-view";

export const metadata: Metadata = { title: "Browse Courses" };

export default function CourseCatalogPage() {
  return <CourseCatalogView />;
}
