import { BookOpen, CalendarDays, LogIn } from "lucide-react";
import type { Student } from "@/types";
import { formatDate, formatRelative } from "@/lib/format";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { UserAvatar } from "@/components/shared/user-avatar";
import { StudentStatusBadge } from "@/components/shared/status-badge";

export function ProfileSummaryCard({ profile }: { profile: Student }) {
  const enrolled = profile.enrolledCourseIds.length;
  return (
    <Card>
      <CardContent className="space-y-5">
        <div className="flex flex-col items-center gap-3 pt-2 text-center">
          <UserAvatar name={profile.name} src={profile.avatarUrl} size="lg" className="size-20 text-xl" />
          <div className="min-w-0 space-y-1">
            <h2 className="truncate text-lg font-semibold">{profile.name}</h2>
            <p className="truncate text-sm text-muted-foreground">{profile.email}</p>
          </div>
          <StudentStatusBadge status={profile.status} />
        </div>
        <Separator />
        <dl className="space-y-3 text-sm">
          <div className="flex items-center justify-between gap-3">
            <dt className="flex items-center gap-2 text-muted-foreground">
              <CalendarDays className="size-4" aria-hidden />
              Member since
            </dt>
            <dd className="font-medium tabular-nums">{formatDate(profile.createdAt)}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="flex items-center gap-2 text-muted-foreground">
              <LogIn className="size-4" aria-hidden />
              Last login
            </dt>
            <dd className="font-medium tabular-nums">
              {profile.lastLoginAt ? formatRelative(profile.lastLoginAt) : "Never"}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="flex items-center gap-2 text-muted-foreground">
              <BookOpen className="size-4" aria-hidden />
              Enrolled courses
            </dt>
            <dd className="font-medium tabular-nums">{enrolled}</dd>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
