import { format, formatDistanceToNowStrict, isValid, parseISO } from "date-fns";

/** Formats minor units (cents) as currency. */
export function formatCurrency(minor: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: minor % 100 === 0 ? 0 : 2,
    maximumFractionDigits: 2,
  }).format(minor / 100);
}

export function formatPrice(minor: number, currency = "USD"): string {
  return minor === 0 ? "Free" : formatCurrency(minor, currency);
}

export function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-US").format(n);
}

export function formatCompactNumber(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

function toDate(value: string | Date | undefined | null): Date | null {
  if (!value) return null;
  const d = typeof value === "string" ? parseISO(value) : value;
  return isValid(d) ? d : null;
}

export function formatDate(value: string | Date | undefined | null, pattern = "MMM d, yyyy"): string {
  const d = toDate(value);
  return d ? format(d, pattern) : "—";
}

export function formatDateTime(value: string | Date | undefined | null): string {
  return formatDate(value, "MMM d, yyyy · h:mm a");
}

export function formatRelative(value: string | Date | undefined | null): string {
  const d = toDate(value);
  return d ? `${formatDistanceToNowStrict(d)} ago` : "—";
}

export function formatDuration(minutes: number): string {
  if (minutes < 60) return `${minutes}m`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h}h ${m}m` : `${h}h`;
}

export function formatAccessDuration(days: number | null): string {
  if (days === null) return "Lifetime access";
  if (days % 365 === 0) return `${days / 365} year${days === 365 ? "" : "s"}`;
  if (days % 30 === 0) return `${days / 30} months`;
  return `${days} days`;
}

export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}

export function daysUntil(value: string | undefined): number | null {
  const d = toDate(value);
  if (!d) return null;
  return Math.ceil((d.getTime() - Date.now()) / 86_400_000);
}
