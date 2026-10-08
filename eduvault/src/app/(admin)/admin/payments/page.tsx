import type { Metadata } from "next";
import { PaymentsView } from "@/components/admin/payments/payments-view";

export const metadata: Metadata = { title: "Payments" };

export default function PaymentsPage() {
  return <PaymentsView />;
}
