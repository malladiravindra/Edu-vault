"use client";

import { useState, type ComponentProps, type ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { AlertCircle, ArrowRight, Eye, EyeOff, Loader2 } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { cn } from "@/lib/utils";

/**
 * Dark-navy form pieces for the hero auth pages (login, register, forgot password).
 * Desktop sizes use vh clamps so a card fits one screen on short windows.
 */

export const heroLinkClass =
  "rounded font-semibold text-[#3b8bff] outline-none hover:underline focus-visible:ring-2 focus-visible:ring-[#3b82f6]";

const inputClass =
  "h-14 w-full rounded-xl border border-[#2b4a8f] bg-[#0f2252]/70 pr-4 text-[15px] text-white outline-none transition-colors placeholder:text-[#8ea3cc] focus:border-[#3b82f6] focus:ring-3 focus:ring-[#3b82f6]/30 aria-invalid:border-red-400 aria-invalid:ring-red-400/20 lg:h-[clamp(42px,5.6vh,56px)]";

export function HeroCardHeader({ title, accent, description }: { title: string; accent: string; description: ReactNode }) {
  return (
    <>
      <h1 className="text-[40px] leading-tight font-bold tracking-tight sm:text-[44px] lg:text-[clamp(28px,4.4vh,44px)]">
        {title} <span className="text-[#3b8bff]">{accent}</span>
      </h1>
      <p className="mt-3 text-lg text-[#c8d4ec] sm:text-xl lg:mt-[clamp(4px,1vh,12px)] lg:text-[clamp(15px,2vh,20px)]">
        {description}
      </p>
    </>
  );
}

export function HeroAlert({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="mt-6 flex items-start gap-2.5 rounded-xl border border-red-400/40 bg-red-500/10 px-4 py-3 text-sm text-red-200"
    >
      <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
      <p>{message}</p>
    </div>
  );
}

interface HeroFieldProps {
  id: string;
  label: string;
  icon: LucideIcon;
  error?: string;
  children: ReactNode;
  after?: ReactNode;
}

/** Label with icon, the control, then an optional error. */
export function HeroField({ id, label, icon: Icon, error, children, after }: HeroFieldProps) {
  return (
    <div className="space-y-3 lg:space-y-[clamp(6px,1vh,12px)]">
      <label htmlFor={id} className="flex items-center gap-2.5 text-lg font-medium lg:text-[clamp(14px,1.8vh,18px)]">
        <Icon className="size-5 text-[#dbe5f7]" aria-hidden />
        {label}
      </label>
      {children}
      {error && (
        <p id={`${id}-error`} className="text-sm text-red-300">
          {error}
        </p>
      )}
      {after}
    </div>
  );
}

export function HeroInput({ icon: Icon, className, ...props }: ComponentProps<"input"> & { icon?: LucideIcon }) {
  return (
    <div className="relative">
      {Icon && (
        <Icon className="pointer-events-none absolute top-1/2 left-5 size-5 -translate-y-1/2 text-[#dbe5f7]" aria-hidden />
      )}
      <input className={cn(inputClass, Icon ? "pl-[3.25rem]" : "pl-5", className)} {...props} />
    </div>
  );
}

export function HeroPasswordInput({ className, ...props }: Omit<ComponentProps<"input">, "type">) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        type={visible ? "text" : "password"}
        placeholder="●●●●●●●"
        className={cn(
          inputClass,
          "pr-14 pl-5 tracking-[0.2em] placeholder:text-xs placeholder:tracking-[0.5em] placeholder:text-white",
          className,
        )}
        {...props}
      />
      <button
        type="button"
        aria-label={visible ? "Hide password" : "Show password"}
        aria-pressed={visible}
        aria-controls={props.id}
        onClick={() => setVisible((v) => !v)}
        className="absolute top-1/2 right-3 flex size-9 -translate-y-1/2 items-center justify-center rounded-lg text-[#dbe5f7] outline-none hover:bg-white/5 focus-visible:ring-2 focus-visible:ring-[#3b82f6]"
      >
        {visible ? <Eye className="size-5" aria-hidden /> : <EyeOff className="size-5" aria-hidden />}
      </button>
    </div>
  );
}

export function HeroCheckbox({ className, ...props }: ComponentProps<typeof Checkbox>) {
  return (
    <Checkbox
      className={cn(
        "size-6 rounded-md border-[#3b5fa8] bg-[#0f2252] data-checked:border-[#2f6bff] data-checked:bg-[#2f6bff] data-checked:text-white dark:data-checked:bg-[#2f6bff] [&_svg]:size-4",
        className,
      )}
      {...props}
    />
  );
}

interface HeroButtonProps extends ComponentProps<"button"> {
  pending?: boolean;
  pendingLabel?: string;
  variant?: "primary" | "outline";
  arrow?: boolean;
}

export function HeroButton({
  pending,
  pendingLabel,
  variant = "primary",
  arrow = variant === "primary",
  className,
  children,
  ...props
}: HeroButtonProps) {
  return (
    <button
      disabled={pending || props.disabled}
      className={cn(
        "flex h-[62px] w-full items-center justify-center gap-3 rounded-xl text-xl outline-none focus-visible:ring-3 focus-visible:ring-[#3b82f6]/50 disabled:cursor-not-allowed disabled:opacity-70 lg:h-[clamp(44px,6vh,62px)] lg:text-[clamp(16px,2vh,20px)]",
        variant === "primary"
          ? "bg-[linear-gradient(90deg,#2563eb_0%,#3b82f6_100%)] font-semibold shadow-[0_10px_30px_rgba(37,99,235,0.35)] transition-[filter,transform] hover:brightness-110 active:scale-[0.99]"
          : "gap-4 border border-[#c8d4ec]/80 font-medium transition-colors hover:bg-white/5",
        className,
      )}
      {...props}
    >
      {pending ? (
        <>
          <Loader2 className="size-5 animate-spin" aria-hidden />
          {pendingLabel}
        </>
      ) : (
        <>
          {children}
          {arrow && <ArrowRight className="size-6" aria-hidden />}
        </>
      )}
    </button>
  );
}

export function HeroDivider() {
  return (
    <div
      className="my-8 flex items-center gap-8 text-lg text-[#c8d4ec] lg:my-[clamp(10px,2.6vh,32px)] lg:text-base"
      role="separator"
      aria-label="or"
    >
      <span className="h-px flex-1 bg-[#3b5fa8]/70" />
      or
      <span className="h-px flex-1 bg-[#3b5fa8]/70" />
    </div>
  );
}

export function HeroFooter({ children }: { children: ReactNode }) {
  return (
    <p className="mt-12 text-center text-base text-[#dbe5f7] lg:mt-[clamp(14px,3.5vh,48px)]">{children}</p>
  );
}

/** Replaces a form once it has been submitted. */
export function HeroStatus({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: LucideIcon;
  title: string;
  description: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div role="status" className="space-y-6">
      <span className="flex size-16 items-center justify-center rounded-full border-2 border-[#2f5bd0] bg-[#0b1f55] shadow-[0_0_24px_rgba(47,107,255,0.3)]">
        <Icon className="size-8 text-[#3b8bff]" aria-hidden />
      </span>
      <div className="space-y-3">
        <h1 className="text-[34px] leading-tight font-bold tracking-tight">{title}</h1>
        <p className="text-lg text-[#c8d4ec]">{description}</p>
      </div>
      {children}
    </div>
  );
}

export function EduVaultLogo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 72" className={className} aria-hidden>
      <defs>
        <linearGradient id="ev-shield" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#3b8bff" />
          <stop offset="100%" stopColor="#1d4fd8" />
        </linearGradient>
      </defs>
      <path d="M32 2 60 12v22c0 17-12 29-28 36C16 63 4 51 4 34V12L32 2Z" fill="#fff" />
      <path d="M32 8 54 16v18c0 13.5-9.2 23.5-22 29.5C19.2 57.5 10 47.5 10 34V16L32 8Z" fill="url(#ev-shield)" />
      <path d="M32 24 50 32 32 40 14 32 32 24Z" fill="#fff" />
      <path d="M21 36v7c0 3 5 6 11 6s11-3 11-6v-7l-11 5-11-5Z" fill="#fff" />
      <path d="M48 33v9" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden>
      <path fill="#FFC107" d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.3-.1-2.4-.4-3.5Z" />
      <path fill="#FF3D00" d="m6.3 14.7 6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.8 1.2 7.9 3l5.7-5.7C34 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7Z" />
      <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44Z" />
      <path fill="#1976D2" d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C37 39.2 44 34 44 24c0-1.3-.1-2.4-.4-3.5Z" />
    </svg>
  );
}
