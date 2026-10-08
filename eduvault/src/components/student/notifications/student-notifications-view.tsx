"use client";

import type { NotificationType } from "@/types";
import { PageHeader } from "@/components/shared/page-header";
import { NotificationCenter } from "@/components/shared/notification-center";

const STUDENT_NOTIFICATION_TYPES: NotificationType[] = [
  "registration",
  "access",
  "payment",
  "resource",
  "course",
  "security",
];

export function StudentNotificationsView() {
  return (
    <div className="space-y-6">
      <PageHeader title="Notifications" description="Updates about your registrations, payments and courses" />
      <NotificationCenter scope="student" types={STUDENT_NOTIFICATION_TYPES} />
    </div>
  );
}
