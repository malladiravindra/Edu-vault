"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, Maximize, Minimize, Minus, Plus, ScanLine, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface PdfToolbarProps {
  title: string;
  subtitle?: string;
  page: number;
  pageCount: number;
  zoomPercent: number;
  canZoomIn: boolean;
  canZoomOut: boolean;
  isFullscreen: boolean;
  onPageChange: (page: number) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onToggleFullscreen: () => void;
}

function ToolButton({ label, onClick, disabled, children }: { label: string; onClick: () => void; disabled?: boolean; children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger render={<Button variant="ghost" size="icon-sm" onClick={onClick} disabled={disabled} aria-label={label} />}>
        {children}
      </TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

export function PdfToolbar({
  title,
  subtitle,
  page,
  pageCount,
  zoomPercent,
  canZoomIn,
  canZoomOut,
  isFullscreen,
  onPageChange,
  onZoomIn,
  onZoomOut,
  onFit,
  onToggleFullscreen,
}: PdfToolbarProps) {
  const [draft, setDraft] = useState(String(page));
  const [syncedPage, setSyncedPage] = useState(page);
  // Keep the input in sync when the page changes from buttons/keyboard.
  if (page !== syncedPage) {
    setSyncedPage(page);
    setDraft(String(page));
  }

  const commit = () => {
    const n = Number.parseInt(draft, 10);
    if (Number.isFinite(n)) onPageChange(Math.min(pageCount, Math.max(1, n)));
    else setDraft(String(page));
  };

  return (
    <div className="flex flex-wrap items-center gap-2 border-b bg-card px-3 py-2">
      <div className="mr-auto flex min-w-0 items-center gap-2">
        <ShieldCheck className="size-4 shrink-0 text-success" aria-hidden />
        <div className="min-w-0">
          <p className="truncate text-sm font-medium">{title}</p>
          {subtitle && <p className="hidden truncate text-xs text-muted-foreground sm:block">{subtitle}</p>}
        </div>
      </div>

      <div className="flex items-center gap-1" role="group" aria-label="Page navigation">
        <ToolButton label="Previous page" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
          <ChevronLeft />
        </ToolButton>
        <div className="flex items-center gap-1.5 text-sm">
          <Input
            value={draft}
            onChange={(e) => setDraft(e.target.value.replace(/\D/g, ""))}
            onBlur={commit}
            onKeyDown={(e) => e.key === "Enter" && commit()}
            inputMode="numeric"
            aria-label={`Page number, of ${pageCount}`}
            className="h-7 w-12 px-1 text-center tabular-nums"
          />
          <span className="text-muted-foreground tabular-nums">/ {pageCount}</span>
        </div>
        <ToolButton label="Next page" onClick={() => onPageChange(page + 1)} disabled={page >= pageCount}>
          <ChevronRight />
        </ToolButton>
      </div>

      <Separator orientation="vertical" className="hidden h-5 data-[orientation=vertical]:self-center sm:block" />

      <div className="flex items-center gap-1" role="group" aria-label="Zoom">
        <ToolButton label="Zoom out" onClick={onZoomOut} disabled={!canZoomOut}>
          <Minus />
        </ToolButton>
        <span className="w-12 text-center text-sm tabular-nums" aria-live="polite">
          {zoomPercent}%
        </span>
        <ToolButton label="Zoom in" onClick={onZoomIn} disabled={!canZoomIn}>
          <Plus />
        </ToolButton>
        <ToolButton label="Fit to screen" onClick={onFit}>
          <ScanLine />
        </ToolButton>
        <ToolButton label={isFullscreen ? "Exit full screen" : "Full screen"} onClick={onToggleFullscreen}>
          {isFullscreen ? <Minimize /> : <Maximize />}
        </ToolButton>
      </div>
    </div>
  );
}
