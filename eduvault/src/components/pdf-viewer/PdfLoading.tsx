import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export function PdfLoading({ label = "Preparing secure document…", className }: { label?: string; className?: string }) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={cn("flex h-full min-h-80 flex-col items-center justify-center gap-3 text-sm text-muted-foreground", className)}
    >
      <Loader2 className="size-6 animate-spin text-primary" aria-hidden />
      {label}
    </div>
  );
}

/** Placeholder with page proportions while a page image loads. */
export function PdfPageSkeleton({ width, height }: { width: number; height: number }) {
  return (
    <div
      className="flex animate-pulse flex-col gap-3 bg-white p-[8%] shadow-sm"
      style={{ width, height }}
      aria-hidden
    >
      <div className="h-[3%] w-1/2 rounded bg-slate-200" />
      {Array.from({ length: 12 }, (_, i) => (
        <div key={i} className="h-[1.4%] rounded bg-slate-100" style={{ width: `${70 + ((i * 17) % 30)}%` }} />
      ))}
    </div>
  );
}
