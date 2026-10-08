"use client";

import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { PlatformSettings } from "@/types";
import { notify } from "@/lib/toast";
import { useUpdateSettings } from "@/hooks/use-settings";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { ConfirmationDialog } from "@/components/shared/confirmation-dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { platformSchema, type PlatformValues } from "./settings-schema";
import { SettingsCard, SwitchRow } from "./settings-card";

const CURRENCIES = [
  { value: "USD", label: "USD — US Dollar" },
  { value: "EUR", label: "EUR — Euro" },
  { value: "GBP", label: "GBP — British Pound" },
  { value: "INR", label: "INR — Indian Rupee" },
];

const TIMEZONES = [
  { value: "UTC", label: "UTC" },
  { value: "America/New_York", label: "America/New_York (Eastern)" },
  { value: "America/Chicago", label: "America/Chicago (Central)" },
  { value: "America/Los_Angeles", label: "America/Los_Angeles (Pacific)" },
  { value: "Europe/London", label: "Europe/London" },
  { value: "Europe/Berlin", label: "Europe/Berlin" },
  { value: "Asia/Kolkata", label: "Asia/Kolkata (IST)" },
  { value: "Asia/Singapore", label: "Asia/Singapore" },
  { value: "Australia/Sydney", label: "Australia/Sydney" },
];

/** Keep the saved value selectable even if it isn't in the predefined list. */
function withCurrent(options: { value: string; label: string }[], current: string) {
  return current && !options.some((o) => o.value === current) ? [...options, { value: current, label: current }] : options;
}

export function PlatformSettingsForm({ settings }: { settings: PlatformSettings }) {
  const update = useUpdateSettings("platform");
  const [pending, setPending] = useState<PlatformValues | null>(null);
  const form = useForm<PlatformValues>({ resolver: zodResolver(platformSchema), values: settings });
  const {
    register,
    control,
    formState: { errors, isDirty },
  } = form;

  function save(values: PlatformValues) {
    update.mutate(values, {
      onSuccess: () => {
        setPending(null);
        notify.success("Platform settings saved", "Changes apply across the platform immediately.");
      },
      onError: (err) => notify.error(err, "Couldn't save platform settings"),
    });
  }

  const onSubmit = form.handleSubmit((values) => {
    if (values.maintenanceMode && !settings.maintenanceMode) {
      setPending(values);
      return;
    }
    save(values);
  });

  const currencyItems = withCurrent(CURRENCIES, settings.defaultCurrency);
  const timezoneItems = withCurrent(TIMEZONES, settings.timezone);

  return (
    <>
      <SettingsCard
        id="platform"
        title="Platform Settings"
        description="General configuration for your EduVault workspace."
        onSubmit={onSubmit}
        onDiscard={() => form.reset()}
        isDirty={isDirty}
        isPending={update.isPending}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField id="platformName" label="Platform name" error={errors.platformName?.message} required>
            <Input
              id="platformName"
              aria-invalid={!!errors.platformName}
              aria-describedby={fieldDescribedBy("platformName", errors.platformName)}
              {...register("platformName")}
            />
          </FormField>
          <FormField
            id="supportEmail"
            label="Support email"
            error={errors.supportEmail?.message}
            description="Shown to students on help pages and emails."
            required
          >
            <Input
              id="supportEmail"
              type="email"
              autoComplete="email"
              aria-invalid={!!errors.supportEmail}
              aria-describedby={fieldDescribedBy("supportEmail", errors.supportEmail, true)}
              {...register("supportEmail")}
            />
          </FormField>
          <FormField id="defaultCurrency" label="Default currency" error={errors.defaultCurrency?.message}>
            <Controller
              control={control}
              name="defaultCurrency"
              render={({ field }) => (
                <Select items={currencyItems} value={field.value} onValueChange={(v) => v && field.onChange(v)}>
                  <SelectTrigger id="defaultCurrency" className="w-full" onBlur={field.onBlur}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {currencyItems.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FormField>
          <FormField id="timezone" label="Timezone" error={errors.timezone?.message}>
            <Controller
              control={control}
              name="timezone"
              render={({ field }) => (
                <Select items={timezoneItems} value={field.value} onValueChange={(v) => v && field.onChange(v)}>
                  <SelectTrigger id="timezone" className="w-full" onBlur={field.onBlur}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {timezoneItems.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FormField>
        </div>

        <Separator />

        <Controller
          control={control}
          name="allowSelfRegistration"
          render={({ field }) => (
            <SwitchRow
              id="allowSelfRegistration"
              title="Allow self-registration"
              description="Let new students create an account from the sign-up page. When off, only admins can add students."
              checked={field.value}
              onCheckedChange={field.onChange}
            />
          )}
        />
        <Controller
          control={control}
          name="maintenanceMode"
          render={({ field }) => (
            <SwitchRow
              id="maintenanceMode"
              tone="warning"
              title="Maintenance mode"
              description="Temporarily blocks student access to the portal and shows a maintenance notice. Admins can still sign in."
              checked={field.value}
              onCheckedChange={field.onChange}
            />
          )}
        />
      </SettingsCard>

      <ConfirmationDialog
        open={pending !== null}
        onOpenChange={(open) => !open && setPending(null)}
        title="Enable maintenance mode?"
        description="Students will be signed out of the portal and won't be able to access courses or resources until maintenance mode is turned off."
        confirmLabel="Enable and save"
        destructive
        loading={update.isPending}
        onConfirm={() => pending && save(pending)}
      />
    </>
  );
}
