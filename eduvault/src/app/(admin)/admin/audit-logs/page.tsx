import type { Metadata } from "next";
import { AuditLogsView } from "@/components/admin/audit-logs/audit-logs-view";

export const metadata: Metadata = { title: "Audit Logs" };

export default function AuditLogsPage() {
  return <AuditLogsView />;
}
