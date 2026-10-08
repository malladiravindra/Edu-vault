"use client";

import { FileWarning, Lock, RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, getErrorMessage } from "@/lib/api/client";

interface PdfErrorProps {
  error: unknown;
  onRetry?: () => void;
}

export function PdfError({ error, onRetry }: PdfErrorProps) {
  const forbidden = error instanceof ApiError && (error.status === 401 || error.status === 403);
  const Icon = forbidden ? Lock : FileWarning;
  return (
    <div role="alert" className="flex h-full min-h-80 flex-col items-center justify-center gap-3 p-6 text-center">
      <div className="flex size-11 items-center justify-center rounded-full bg-destructive/10 text-destructive">
        <Icon className="size-5" aria-hidden />
      </div>
      <div className="space-y-1">
        <p className="text-sm font-semibold">{forbidden ? "Access not available" : "This document couldn't be displayed"}</p>
        <p className="max-w-sm text-sm text-muted-foreground">{getErrorMessage(error)}</p>
      </div>
      {onRetry && !forbidden && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RotateCw />
          Try again
        </Button>
      )}
    </div>
  );
}
