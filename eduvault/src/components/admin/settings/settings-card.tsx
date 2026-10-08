"use client";

import type { FormEventHandler, ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

interface SettingsCardProps {
  id: string;
  title: string;
  description: string;
  onSubmit: FormEventHandler<HTMLFormElement>;
  onDiscard: () => void;
  isDirty: boolean;
  isPending: boolean;
  submitLabel?: string;
  /** Require a dirty form before saving (default true). */
  requireDirty?: boolean;
  children: ReactNode;
}

/** Card frame for a settings section: header, form body, and Save/Discard footer. */
export function SettingsCard({
  id,
  title,
  description,
  onSubmit,
  onDiscard,
  isDirty,
  isPending,
  submitLabel = "Save changes",
  requireDirty = true,
  children,
}: SettingsCardProps) {
  const headingId = `${id}-title`;
  return (
    <Card>
      <form onSubmit={onSubmit} noValidate aria-labelledby={headingId} className="flex flex-col gap-(--card-spacing)">
        <CardHeader className="border-b">
          <CardTitle id={headingId} role="heading" aria-level={2} className="text-base font-semibold">
            {title}
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">{children}</CardContent>
        <CardFooter className="justify-end gap-2">
          <Button type="button" variant="ghost" onClick={onDiscard} disabled={!isDirty || isPending}>
            Discard
          </Button>
          <Button type="submit" disabled={(requireDirty && !isDirty) || isPending}>
            {isPending && <Loader2 className="animate-spin" />}
            {submitLabel}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}

interface SwitchRowProps {
  id: string;
  title: string;
  description: ReactNode;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  tone?: "default" | "warning";
  className?: string;
}

/** Title + description on the left, Switch on the right. */
export function SwitchRow({ id, title, description, checked, onCheckedChange, disabled, tone = "default", className }: SwitchRowProps) {
  return (
    <div
      className={cn(
        "flex items-start justify-between gap-4 rounded-lg",
        tone === "warning" && "border border-warning/40 bg-warning/5 p-3",
        className,
      )}
    >
      <div className="min-w-0 space-y-0.5">
        <label htmlFor={id} className="text-sm font-medium">
          {title}
        </label>
        <p id={`${id}-description`} className="text-sm text-muted-foreground">
          {description}
        </p>
      </div>
      <Switch
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        aria-describedby={`${id}-description`}
        className="mt-0.5"
      />
    </div>
  );
}
