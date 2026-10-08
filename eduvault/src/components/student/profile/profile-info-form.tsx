"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import type { Student } from "@/types";
import { notify } from "@/lib/toast";
import { useUpdateProfile } from "@/hooks/use-students";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { profileSchema, type ProfileValues } from "./profile-schemas";

export function ProfileInfoForm({ profile }: { profile: Student }) {
  const update = useUpdateProfile();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<ProfileValues>({
    resolver: zodResolver(profileSchema),
    // `values` keeps the form in sync with the latest server profile.
    values: { name: profile.name, phone: profile.phone ?? "" },
  });

  const onSubmit = handleSubmit((values) => {
    update.mutate(
      { name: values.name, phone: values.phone || undefined },
      {
        onSuccess: () => notify.success("Profile updated"),
        onError: (err) => notify.error(err, "Couldn't update profile"),
      },
    );
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Profile information</h2>
        </CardTitle>
        <CardDescription>Your name and contact details as shown to course administrators.</CardDescription>
      </CardHeader>
      <form onSubmit={onSubmit} noValidate className="contents">
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <FormField id="profile-name" label="Full name" error={errors.name?.message} required className="sm:col-span-2">
            <Input
              id="profile-name"
              autoComplete="name"
              aria-invalid={!!errors.name}
              aria-describedby={fieldDescribedBy("profile-name", errors.name)}
              {...register("name")}
            />
          </FormField>
          <FormField
            id="profile-email"
            label="Email"
            description="Contact support to change your email address"
          >
            <Input
              id="profile-email"
              type="email"
              value={profile.email}
              readOnly
              disabled
              aria-describedby={fieldDescribedBy("profile-email", undefined, true)}
            />
          </FormField>
          <FormField id="profile-phone" label="Phone" error={errors.phone?.message} description="Optional">
            <Input
              id="profile-phone"
              type="tel"
              autoComplete="tel"
              placeholder="+1 555 123 4567"
              aria-invalid={!!errors.phone}
              aria-describedby={fieldDescribedBy("profile-phone", errors.phone, true)}
              {...register("phone")}
            />
          </FormField>
        </CardContent>
        <CardFooter className="justify-end gap-2">
          <Button type="button" variant="ghost" onClick={() => reset()} disabled={!isDirty || update.isPending}>
            Discard
          </Button>
          <Button type="submit" disabled={!isDirty || update.isPending}>
            {update.isPending && <Loader2 className="animate-spin" />}
            Save changes
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
