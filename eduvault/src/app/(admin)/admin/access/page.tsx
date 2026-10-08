import type { Metadata } from "next";
import { AccessView } from "@/components/admin/access/access-view";

export const metadata: Metadata = { title: "Access Management" };

export default function AccessPage() {
  return <AccessView />;
}
