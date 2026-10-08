"use client";

import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { NotificationPreferences } from "@/types";
import { notify } from "@/lib/toast";
import { useUpdateSettings } from "@/hooks/use-settings";
import { notificationsSchema, type NotificationsValues } from "./settings-schema";
import { SettingsCard, SwitchRow } from "./settings-card";

const ROWS: { key: keyof NotificationsValues; title: string; description: string }[] = [
  {
    key: "emailNewRegistration",
    title: "New registrations",
    description: "Email me when a student registers for a course that needs review or payment.",
  },
  {
    key: "emailPaymentReceived",
    title: "Payments received",
    description: "Email me when a payment is completed or refunded.",
  },
  {
    key: "emailAccessExpiring",
    title: "Access expiring",
    description: "Email me a summary of student access that is about to expire.",
  },
  {
    key: "inAppSystemAlerts",
    title: "In-app system alerts",
    description: "Show security and system alerts in the notification center.",
  },
  {
    key: "weeklyDigest",
    title: "Weekly digest",
    description: "A Monday email with registrations, revenue and course activity for the past week.",
  },
];

export function NotificationSettingsForm({ settings }: { settings: NotificationPreferences }) {
  const update = useUpdateSettings("notifications");
  const form = useForm<NotificationsValues>({ resolver: zodResolver(notificationsSchema), values: settings });

  const onSubmit = form.handleSubmit((values) =>
    update.mutate(values, {
      onSuccess: () => notify.success("Notification preferences saved"),
      onError: (err) => notify.error(err, "Couldn't save notification preferences"),
    }),
  );

  return (
    <SettingsCard
      id="notifications"
      title="Notification Preferences"
      description="Choose which events notify you by email or in the app."
      onSubmit={onSubmit}
      onDiscard={() => form.reset()}
      isDirty={form.formState.isDirty}
      isPending={update.isPending}
    >
      <div className="divide-y">
        {ROWS.map((row) => (
          <Controller
            key={row.key}
            control={form.control}
            name={row.key}
            render={({ field }) => (
              <SwitchRow
                id={`notif-${row.key}`}
                title={row.title}
                description={row.description}
                checked={field.value}
                onCheckedChange={field.onChange}
                className="py-4 first:pt-0 last:pb-0"
              />
            )}
          />
        ))}
      </div>
    </SettingsCard>
  );
}
