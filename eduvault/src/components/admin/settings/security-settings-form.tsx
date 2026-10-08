"use client";

import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { SecuritySettings } from "@/types";
import { notify } from "@/lib/toast";
import { useUpdateSettings } from "@/hooks/use-settings";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { ConfirmationDialog } from "@/components/shared/confirmation-dialog";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { securitySchema, type SecurityValues } from "./settings-schema";
import { SettingsCard, SwitchRow } from "./settings-card";

const TIMEOUT_MINUTES = [15, 30, 60, 120];

function timeoutLabel(minutes: number) {
  return minutes < 60 ? `${minutes} minutes` : minutes === 60 ? "1 hour" : `${minutes / 60} hours`;
}

function timeoutItems(current: number) {
  const values = TIMEOUT_MINUTES.includes(current) ? TIMEOUT_MINUTES : [...TIMEOUT_MINUTES, current].sort((a, b) => a - b);
  return values.map((m) => ({ value: String(m), label: timeoutLabel(m) }));
}

export function SecuritySettingsForm({ settings }: { settings: SecuritySettings }) {
  const update = useUpdateSettings("security");
  const [pending, setPending] = useState<SecurityValues | null>(null);
  const form = useForm<SecurityValues>({ resolver: zodResolver(securitySchema), values: settings });
  const {
    register,
    control,
    formState: { errors, isDirty },
  } = form;

  function save(values: SecurityValues) {
    update.mutate(values, {
      onSuccess: () => {
        setPending(null);
        notify.success("Security settings saved");
      },
      onError: (err) => notify.error(err, "Couldn't save security settings"),
    });
  }

  const onSubmit = form.handleSubmit((values) => {
    if (!values.watermarkEnabled && settings.watermarkEnabled) {
      setPending(values);
      return;
    }
    save(values);
  });

  const items = timeoutItems(settings.sessionTimeoutMinutes);

  return (
    <>
      <SettingsCard
        id="security"
        title="Security"
        description="Sign-in protection and content security for the whole platform."
        onSubmit={onSubmit}
        onDiscard={() => form.reset()}
        isDirty={isDirty}
        isPending={update.isPending}
      >
        <Controller
          control={control}
          name="requireTwoFactorForAdmins"
          render={({ field }) => (
            <SwitchRow
              id="requireTwoFactorForAdmins"
              title="Require two-factor authentication for admins"
              description="Administrators must verify a one-time code each time they sign in."
              checked={field.value}
              onCheckedChange={field.onChange}
            />
          )}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            id="sessionTimeoutMinutes"
            label="Session timeout"
            description="Sign users out after this period of inactivity."
            error={errors.sessionTimeoutMinutes?.message}
          >
            <Controller
              control={control}
              name="sessionTimeoutMinutes"
              render={({ field }) => (
                <Select
                  items={items}
                  value={String(field.value)}
                  onValueChange={(v) => v && field.onChange(Number(v))}
                >
                  <SelectTrigger
                    id="sessionTimeoutMinutes"
                    className="w-full"
                    onBlur={field.onBlur}
                    aria-describedby={fieldDescribedBy("sessionTimeoutMinutes", errors.sessionTimeoutMinutes, true)}
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {items.map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </FormField>
          <FormField
            id="maxLoginAttempts"
            label="Max login attempts"
            description="Lock the account after this many failed attempts (3–10)."
            error={errors.maxLoginAttempts?.message}
            required
          >
            <Input
              id="maxLoginAttempts"
              type="number"
              inputMode="numeric"
              min={3}
              max={10}
              className="tabular-nums"
              aria-invalid={!!errors.maxLoginAttempts}
              aria-describedby={fieldDescribedBy("maxLoginAttempts", errors.maxLoginAttempts, true)}
              {...register("maxLoginAttempts", { valueAsNumber: true })}
            />
          </FormField>
        </div>

        <Separator />

        <Controller
          control={control}
          name="watermarkEnabled"
          render={({ field }) => (
            <SwitchRow
              id="watermarkEnabled"
              title="Watermark protected PDFs"
              description="Stamp each page with the viewer's name, email and a timestamp to discourage sharing."
              checked={field.value}
              onCheckedChange={field.onChange}
            />
          )}
        />
      </SettingsCard>

      <ConfirmationDialog
        open={pending !== null}
        onOpenChange={(open) => !open && setPending(null)}
        title="Turn off PDF watermarking?"
        description="Protected PDFs will no longer be watermarked with the viewer's identity. Leaked copies won't be traceable to a student."
        confirmLabel="Turn off and save"
        destructive
        loading={update.isPending}
        onConfirm={() => pending && save(pending)}
      />
    </>
  );
}
