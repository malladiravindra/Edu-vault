"use client";

import { Progress as ProgressPrimitive } from "@base-ui/react/progress";
import { ProgressIndicator, ProgressTrack } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

interface ProgressBarProps {
  value: number;
  /** Show "NN%" to the right of the bar. */
  showValue?: boolean;
  size?: "sm" | "md";
  label?: string;
  className?: string;
}

/** Consistent progress display (0–100). */
export function ProgressBar({ value, showValue = true, size = "sm", label, className }: ProgressBarProps) {
  const v = Math.round(Math.min(100, Math.max(0, value)));
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <ProgressPrimitive.Root value={v} aria-label={label ?? `${v}% complete`} className="flex-1">
        <ProgressTrack className={size === "md" ? "h-2" : "h-1.5"}>
          <ProgressIndicator className={v === 100 ? "bg-success" : undefined} />
        </ProgressTrack>
      </ProgressPrimitive.Root>
      {showValue && <span className="w-9 text-right text-xs text-muted-foreground tabular-nums">{v}%</span>}
    </div>
  );
}
