import type { ReactNode } from "react";
import { FileText, Lock } from "lucide-react";
import type { Resource } from "@/types";
import { formatFileSize } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ProgressBar } from "./progress-bar";

interface ResourceCardProps {
  resource: Resource;
  /** Locked resources are listed but not openable (no active access). */
  locked?: boolean;
  progress?: number;
  action?: ReactNode;
  className?: string;
}

export function ResourceCard({ resource, locked, progress, action, className }: ResourceCardProps) {
  return (
    <div className={cn("flex items-center gap-4 rounded-lg border bg-card p-4", locked && "opacity-80", className)}>
      <div
        className={cn(
          "flex size-10 shrink-0 items-center justify-center rounded-lg",
          locked ? "bg-muted text-muted-foreground" : "bg-primary/10 text-primary",
        )}
      >
        {locked ? <Lock className="size-4.5" aria-hidden /> : <FileText className="size-4.5" aria-hidden />}
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <p className="truncate text-sm font-medium">{resource.name}</p>
        <p className="text-xs text-muted-foreground">
          PDF · {resource.pageCount} pages · {formatFileSize(resource.fileSizeBytes)}
        </p>
        {progress !== undefined && <ProgressBar value={progress} className="max-w-56 pt-1" />}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
