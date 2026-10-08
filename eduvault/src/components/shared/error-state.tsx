"use client";

import { AlertTriangle, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/lib/api/client";
import { cn } from "@/lib/utils";

interface ErrorStateProps {
  title?: string;
  error?: unknown;
  description?: string;
  onRetry?: () => void;
  retrying?: boolean;
  className?: string;
  compact?: boolean;
}

export function ErrorState({
  title = "We couldn't load this",
  error,
  description,
  onRetry,
  retrying,
  className,
  compact,
}: ErrorStateProps) {
  const message = description ?? (error ? getErrorMessage(error) : "Please check your connection and try again.");
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center text-center",
        compact ? "gap-2 px-4 py-8" : "gap-3 px-6 py-14",
        className,
      )}
    >
      <div className="flex size-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <AlertTriangle className="size-5" aria-hidden />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold">{title}</p>
        <p className="mx-auto max-w-sm text-sm text-muted-foreground">{message}</p>
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} disabled={retrying} className="mt-1">
          <RotateCw className={cn(retrying && "animate-spin")} />
          Try again
        </Button>
      )}
    </div>
  );
}
