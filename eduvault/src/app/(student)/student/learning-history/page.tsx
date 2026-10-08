import type { Metadata } from "next";
import { LearningHistoryView } from "@/components/student/learning-history/learning-history-view";

export const metadata: Metadata = { title: "Learning History" };

export default function LearningHistoryPage() {
  return <LearningHistoryView />;
}
