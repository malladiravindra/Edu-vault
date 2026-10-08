import type { Metadata } from "next";
import { MyCoursesView } from "@/components/student/my-courses/my-courses-view";

export const metadata: Metadata = { title: "My Courses" };

export default function MyCoursesPage() {
  return <MyCoursesView />;
}
