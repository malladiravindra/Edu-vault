import { AlertTriangle } from "lucide-react";
import { daysUntil, formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { EXPIRY_WARNING_DAYS } from "./utils";

interface ExpiryNoteProps {
  expiresAt?: string;
  className?: string;
  /** Render nothing unless the "expires soon" warning applies. */
  warnOnly?: boolean;
}

/** "Expires Mar 3, 2026", or an amber "Expires in N days" warning when close. */
export function ExpiryNote({ expiresAt, className, warnOnly }: ExpiryNoteProps) {
  if (!expiresAt) {
    return warnOnly ? null : <span className={cn("text-xs text-muted-foreground", className)}>Lifetime access</span>;
  }
  const days = daysUntil(expiresAt);
  if (days !== null && days >= 0 && days <= EXPIRY_WARNING_DAYS) {
    return (
      <span className={cn("inline-flex items-center gap-1 text-xs font-medium text-warning", className)}>
        <AlertTriangle className="size-3.5" aria-hidden />
        {days === 0 ? "Expires today" : `Expires in ${days} day${days === 1 ? "" : "s"}`}
      </span>
    );
  }
  if (warnOnly) return null;
  const past = days !== null && days < 0;
  return (
    <span className={cn("text-xs text-muted-foreground tabular-nums", className)}>
      {past ? "Expired" : "Expires"} {formatDate(expiresAt)}
    </span>
  );
}
