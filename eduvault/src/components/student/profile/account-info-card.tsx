import type { ReactNode } from "react";
import type { Student } from "@/types";
import { formatDate, formatDateTime } from "@/lib/format";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StudentStatusBadge } from "@/components/shared/status-badge";

const ROLE_LABEL: Record<Student["role"], string> = { student: "Student" };

export function AccountInfoCard({ profile }: { profile: Student }) {
  const rows: { label: string; value: ReactNode }[] = [
    { label: "Account ID", value: <span className="font-mono text-xs">{profile.id}</span> },
    { label: "Role", value: ROLE_LABEL[profile.role] },
    { label: "Account status", value: <StudentStatusBadge status={profile.status} /> },
    { label: "Member since", value: formatDate(profile.createdAt) },
    { label: "Last sign-in", value: profile.lastLoginAt ? formatDateTime(profile.lastLoginAt) : "Never" },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Account information</h2>
        </CardTitle>
        <CardDescription>Details managed by EduVault. These can&apos;t be edited.</CardDescription>
      </CardHeader>
      <CardContent>
        <dl className="divide-y rounded-lg border">
          {rows.map((row) => (
            <div key={row.label} className="flex flex-col gap-1 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
              <dt className="text-sm text-muted-foreground">{row.label}</dt>
              <dd className="text-sm font-medium tabular-nums">{row.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
