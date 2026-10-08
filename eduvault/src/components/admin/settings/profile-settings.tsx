"use client";

import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Camera } from "lucide-react";
import type { CurrentUser } from "@/types";
import { notify } from "@/lib/toast";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { UserAvatar } from "@/components/shared/user-avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { profileSchema, type ProfileValues } from "./settings-schema";
import { SettingsCard } from "./settings-card";

/** Simulated latency — there is no admin profile endpoint wired yet. */
const wait = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

export function ProfileSettings({ user }: { user: CurrentUser }) {
  const form = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    values: { name: user.name, title: user.role === "admin" ? user.title : "" },
  });
  const {
    register,
    formState: { errors, isDirty, isSubmitting },
  } = form;
  const watchedName = useWatch({ control: form.control, name: "name" });

  const onSubmit = form.handleSubmit(async (values) => {
    // UI-only: no admin profile endpoint exists yet, so simulate the request.
    await wait(700);
    form.reset(values);
    notify.success("Profile updated", "Your profile details have been saved.");
  });

  return (
    <SettingsCard
      id="profile"
      title="Profile"
      description="Your personal details as shown to other administrators."
      onSubmit={onSubmit}
      onDiscard={() => form.reset()}
      isDirty={isDirty}
      isPending={isSubmitting}
    >
      <div className="flex items-center gap-4">
        <UserAvatar name={watchedName || user.name} src={user.avatarUrl} size="lg" />
        <div className="space-y-1">
          <Tooltip>
            <TooltipTrigger render={<span tabIndex={0} className="inline-flex rounded-lg" />}>
              <Button type="button" variant="outline" size="sm" disabled>
                <Camera />
                Change photo
              </Button>
            </TooltipTrigger>
            <TooltipContent>Coming soon</TooltipContent>
          </Tooltip>
          <p className="text-xs text-muted-foreground">JPG or PNG, up to 2 MB.</p>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <FormField id="profile-name" label="Full name" error={errors.name?.message} required>
          <Input
            id="profile-name"
            autoComplete="name"
            aria-invalid={!!errors.name}
            aria-describedby={fieldDescribedBy("profile-name", errors.name)}
            {...register("name")}
          />
        </FormField>
        <FormField id="profile-title" label="Job title" error={errors.title?.message}>
          <Input
            id="profile-title"
            autoComplete="organization-title"
            placeholder="e.g. Platform Administrator"
            aria-invalid={!!errors.title}
            aria-describedby={fieldDescribedBy("profile-title", errors.title)}
            {...register("title")}
          />
        </FormField>
        <FormField
          id="profile-email"
          label="Email"
          description="Contact a super admin to change"
          className="sm:col-span-2"
        >
          <Input
            id="profile-email"
            type="email"
            value={user.email}
            readOnly
            aria-readonly
            className="bg-muted/50 text-muted-foreground"
            aria-describedby={fieldDescribedBy("profile-email", undefined, true)}
          />
        </FormField>
      </div>
    </SettingsCard>
  );
}
