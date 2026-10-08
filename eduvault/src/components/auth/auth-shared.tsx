"use client";

import { useState, type ComponentProps, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AlertCircle, Check, Circle, Eye, EyeOff } from "lucide-react";
import { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput } from "@/components/ui/input-group";
import { cn } from "@/lib/utils";
import { PASSWORD_RULES } from "./auth-schemas";

/** Where a user lands after 2FA. UI routing hint only — the backend enforces roles. */
export function portalForChallenge(challengeId: string): string {
  return challengeId.includes("admin") ? "/admin/dashboard" : "/student/dashboard";
}

/** Only allow same-origin relative redirects. */
export function safeNextPath(next: string | null): string {
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/student/dashboard";
}

export function AuthHeader({ title, description }: { title: string; description?: ReactNode }) {
  return (
    <div className="mb-8 space-y-2">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
    </div>
  );
}

export function AuthErrorAlert({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="mb-6 flex items-start gap-2.5 rounded-lg border border-destructive/30 bg-destructive/5 px-3.5 py-3 text-sm text-destructive"
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p>{message}</p>
    </div>
  );
}

interface AuthStatusProps {
  icon: LucideIcon;
  tone?: "success" | "destructive";
  title: string;
  description: ReactNode;
  children?: ReactNode;
}

/** Replaces a form once it has been submitted (or when a link is invalid). */
export function AuthStatus({ icon: Icon, tone = "success", title, description, children }: AuthStatusProps) {
  return (
    <div className="space-y-6" role="status">
      <div
        className={cn(
          "flex size-12 items-center justify-center rounded-full",
          tone === "success" ? "bg-success/10 text-success" : "bg-destructive/10 text-destructive",
        )}
      >
        <Icon className="size-6" aria-hidden />
      </div>
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>
      {children}
    </div>
  );
}

type PasswordInputProps = Omit<ComponentProps<"input">, "type">;

export function PasswordInput({ className, ...props }: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  return (
    <InputGroup className={className}>
      <InputGroupInput type={visible ? "text" : "password"} {...props} />
      <InputGroupAddon align="inline-end">
        <InputGroupButton
          size="icon-xs"
          aria-label={visible ? "Hide password" : "Show password"}
          aria-pressed={visible}
          aria-controls={props.id}
          onClick={() => setVisible((v) => !v)}
        >
          {visible ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  );
}

export function PasswordChecklist({ value, id }: { value: string; id?: string }) {
  return (
    <ul id={id} className="grid gap-1 text-xs" aria-label="Password requirements">
      {PASSWORD_RULES.map((rule) => {
        const met = rule.test(value);
        return (
          <li
            key={rule.id}
            className={cn("flex items-center gap-1.5", met ? "text-success" : "text-muted-foreground")}
          >
            {met ? <Check className="size-3.5" aria-hidden /> : <Circle className="size-3" aria-hidden />}
            {rule.label}
            <span className="sr-only">{met ? "(met)" : "(not met)"}</span>
          </li>
        );
      })}
    </ul>
  );
}
