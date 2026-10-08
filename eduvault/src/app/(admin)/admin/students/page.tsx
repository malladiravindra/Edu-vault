import type { Metadata } from "next";
import { StudentsView } from "@/components/admin/students/students-view";

export const metadata: Metadata = { title: "Students" };

export default function StudentsPage() {
  return <StudentsView />;
}
