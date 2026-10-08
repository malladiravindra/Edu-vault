import type { Metadata } from "next";
import { RegistrationsView } from "@/components/admin/registrations/registrations-view";

export const metadata: Metadata = { title: "Registrations" };

export default function RegistrationsPage() {
  return <RegistrationsView />;
}
