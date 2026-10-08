import type { Metadata } from "next";
import { CheckoutView, type CheckoutResultStatus } from "@/components/student/payments/checkout-view";

export const metadata: Metadata = { title: "Checkout" };

const RESULT_STATUSES: readonly CheckoutResultStatus[] = ["success", "failed", "cancelled", "pending"];

interface CheckoutPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function first(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export default async function CheckoutPage({ searchParams }: CheckoutPageProps) {
  const query = await searchParams;
  const courseId = first(query.course)?.trim() || undefined;
  const rawStatus = first(query.status);
  const status = RESULT_STATUSES.find((s) => s === rawStatus);
  // Keyed so a status change (e.g. "Try again") resets local view state.
  return <CheckoutView key={`${courseId}-${status ?? "summary"}`} courseId={courseId} status={status} />;
}
