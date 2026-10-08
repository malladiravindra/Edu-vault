"use client";

import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import type { AccessDefaults, AccessModel } from "@/types";
import { formatAccessDuration } from "@/lib/format";
import { notify } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { useUpdateSettings } from "@/hooks/use-settings";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { accessDefaultsSchema, type AccessDefaultsValues } from "./settings-schema";
import { SettingsCard, SwitchRow } from "./settings-card";

const ACCESS_MODELS: { value: AccessModel; title: string; description: string }[] = [
  { value: "free", title: "Free", description: "Students get instant access after registering." },
  { value: "paid", title: "Paid", description: "Access is granted once payment succeeds." },
  { value: "approval", title: "Approval", description: "An admin reviews each registration before access." },
];

const LIFETIME = "lifetime";
const DURATION_DAYS = [30, 90, 180, 365];

function durationItems(current: number | null) {
  const days = current !== null && !DURATION_DAYS.includes(current) ? [...DURATION_DAYS, current].sort((a, b) => a - b) : DURATION_DAYS;
  return [
    ...days.map((d) => ({ value: String(d), label: formatAccessDuration(d) })),
    { value: LIFETIME, label: formatAccessDuration(null) },
  ];
}

export function AccessDefaultsForm({ settings }: { settings: AccessDefaults }) {
  const update = useUpdateSettings("accessDefaults");
  const form = useForm<AccessDefaultsValues>({ resolver: zodResolver(accessDefaultsSchema), values: settings });
  const {
    register,
    control,
    formState: { errors, isDirty },
  } = form;

  const onSubmit = form.handleSubmit((values) =>
    update.mutate(values, {
      onSuccess: () => notify.success("Access defaults saved", "New courses will use these defaults."),
      onError: (err) => notify.error(err, "Couldn't save access defaults"),
    }),
  );

  const items = durationItems(settings.defaultAccessDurationDays);

  return (
    <SettingsCard
      id="access-defaults"
      title="Access Defaults"
      description="Defaults applied when creating new courses. Each course can override them."
      onSubmit={onSubmit}
      onDiscard={() => form.reset()}
      isDirty={isDirty}
      isPending={update.isPending}
    >
      <fieldset className="space-y-2">
        <legend className="mb-2 text-sm font-medium">Default access model</legend>
        <Controller
          control={control}
          name="defaultAccessModel"
          render={({ field }) => (
            <RadioGroup
              value={field.value}
              onValueChange={(v) => field.onChange(v as AccessModel)}
              className="grid gap-3 sm:grid-cols-3"
            >
              {ACCESS_MODELS.map((m) => (
                <label
                  key={m.value}
                  className={cn(
                    "flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/40",
                    field.value === m.value && "border-primary bg-primary/5",
                  )}
                >
                  <RadioGroupItem value={m.value} className="mt-0.5" />
                  <span className="space-y-0.5">
                    <span className="block text-sm font-medium">{m.title}</span>
                    <span className="block text-xs text-muted-foreground">{m.description}</span>
                  </span>
                </label>
              ))}
            </RadioGroup>
          )}
        />
      </fieldset>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField
          id="defaultAccessDurationDays"
          label="Default access duration"
          description="How long students keep access after it's granted."
          error={errors.defaultAccessDurationDays?.message}
        >
          <Controller
            control={control}
            name="defaultAccessDurationDays"
            render={({ field }) => (
              <Select
                items={items}
                value={field.value === null ? LIFETIME : String(field.value)}
                onValueChange={(v) => {
                  if (!v) return;
                  field.onChange(v === LIFETIME ? null : Number(v));
                }}
              >
                <SelectTrigger
                  id="defaultAccessDurationDays"
                  className="w-full"
                  onBlur={field.onBlur}
                  aria-describedby={fieldDescribedBy("defaultAccessDurationDays", errors.defaultAccessDurationDays, true)}
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
          id="expiryReminderDays"
          label="Expiry reminder (days before)"
          description="Between 1 and 60 days."
          error={errors.expiryReminderDays?.message}
          required
        >
          <Input
            id="expiryReminderDays"
            type="number"
            inputMode="numeric"
            min={1}
            max={60}
            className="tabular-nums"
            aria-invalid={!!errors.expiryReminderDays}
            aria-describedby={fieldDescribedBy("expiryReminderDays", errors.expiryReminderDays, true)}
            {...register("expiryReminderDays", { valueAsNumber: true })}
          />
        </FormField>
      </div>

      <Separator />

      <Controller
        control={control}
        name="autoApproveFreeCourses"
        render={({ field }) => (
          <SwitchRow
            id="autoApproveFreeCourses"
            title="Auto-approve free courses"
            description="Grant access immediately when a student registers for a free course, without admin review."
            checked={field.value}
            onCheckedChange={field.onChange}
          />
        )}
      />
    </SettingsCard>
  );
}
