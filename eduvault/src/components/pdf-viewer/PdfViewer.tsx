"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { ID } from "@/types";
import { resourceApi } from "@/lib/api/resourceApi";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { queryKeys } from "@/hooks/query-keys";
import { useViewerSession } from "@/hooks/use-resources";
import { useRecordProgress } from "@/hooks/use-learning";
import { PAGE_BASE_HEIGHT, PAGE_BASE_WIDTH, PdfPage } from "./PdfPage";
import { PdfToolbar } from "./PdfToolbar";
import { PdfLoading } from "./PdfLoading";
import { PdfError } from "./PdfError";

const MIN_SCALE = 0.4;
const MAX_SCALE = 2.5;
const ZOOM_STEP = 0.15;
const VIEWPORT_PADDING = 32;

interface PdfViewerProps {
  resourceId: ID;
  /** "admin-preview" skips access checks client-side and progress reporting. */
  mode?: "student" | "admin-preview";
  initialPage?: number;
  onPageChange?: (page: number) => void;
  className?: string;
}

/**
 * Protected document viewer. Renders server-provided page images one at a
 * time with a dynamic watermark; it never receives a PDF file or URL.
 *
 * Keyboard: ←/→ or PageUp/PageDown change page, +/− zoom, 0 fits to screen.
 */
export function PdfViewer({ resourceId, mode = "student", initialPage = 1, onPageChange, className }: PdfViewerProps) {
  const session = useViewerSession(resourceId, mode);
  const queryClient = useQueryClient();
  const recordProgress = useRecordProgress();

  const rootRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(initialPage);
  const [scale, setScale] = useState(1);
  const [autoFit, setAutoFit] = useState(true);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [issuedAt] = useState(() => formatDateTime(new Date()));
  const pageEnteredAt = useRef(0);

  const pageCount = session.data?.pageCount ?? 1;

  const fitToScreen = useCallback(() => {
    const el = viewportRef.current;
    if (!el) return;
    const w = (el.clientWidth - VIEWPORT_PADDING) / PAGE_BASE_WIDTH;
    const h = (el.clientHeight - VIEWPORT_PADDING) / PAGE_BASE_HEIGHT;
    // On narrow screens fit width; otherwise fit the whole page.
    const next = el.clientWidth < 640 ? w : Math.min(w, h);
    setScale(Math.min(MAX_SCALE, Math.max(MIN_SCALE, Number(next.toFixed(3)))));
  }, []);

  // Refit on resize while in auto-fit mode.
  useEffect(() => {
    const el = viewportRef.current;
    if (!el || !autoFit) return;
    const ro = new ResizeObserver(() => fitToScreen());
    ro.observe(el);
    return () => ro.disconnect();
  }, [autoFit, fitToScreen, session.data]);

  const goTo = useCallback(
    (next: number) => {
      const clamped = Math.min(pageCount, Math.max(1, next));
      setPage(clamped);
      onPageChange?.(clamped);
      viewportRef.current?.scrollTo({ top: 0 });
    },
    [pageCount, onPageChange],
  );

  const zoom = useCallback((delta: number) => {
    setAutoFit(false);
    setScale((s) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, Number((s + delta).toFixed(2)))));
  }, []);

  const fit = useCallback(() => {
    setAutoFit(true);
    fitToScreen();
  }, [fitToScreen]);

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) void document.exitFullscreen();
    else void rootRef.current?.requestFullscreen?.();
  }, []);

  useEffect(() => {
    const onChange = () => {
      setIsFullscreen(document.fullscreenElement === rootRef.current);
    };
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  // Prefetch the next page for snappy navigation.
  useEffect(() => {
    if (!session.data || page >= pageCount) return;
    void queryClient.prefetchQuery({
      queryKey: queryKeys.resources.page(resourceId, page + 1),
      queryFn: () => resourceApi.getPage(resourceId, page + 1),
      staleTime: 60_000,
    });
  }, [page, pageCount, resourceId, session.data, queryClient]);

  // Report time spent on each page (student mode only).
  const { mutate: report } = recordProgress;
  useEffect(() => {
    if (mode !== "student" || !session.data) return;
    pageEnteredAt.current = Date.now();
    return () => {
      const seconds = Math.round((Date.now() - pageEnteredAt.current) / 1000);
      if (seconds >= 2) report({ resourceId, page, secondsSpent: seconds });
    };
  }, [page, mode, resourceId, session.data, report]);

  const onKeyDown = (e: React.KeyboardEvent) => {
    if ((e.target as HTMLElement).tagName === "INPUT") return;
    if (e.key === "ArrowRight" || e.key === "PageDown") {
      e.preventDefault();
      goTo(page + 1);
    } else if (e.key === "ArrowLeft" || e.key === "PageUp") {
      e.preventDefault();
      goTo(page - 1);
    } else if (e.key === "+" || e.key === "=") {
      zoom(ZOOM_STEP);
    } else if (e.key === "-") {
      zoom(-ZOOM_STEP);
    } else if (e.key === "0") {
      fit();
    }
  };

  return (
    <div
      ref={rootRef}
      className={cn(
        "protected-content flex flex-col overflow-hidden rounded-xl border bg-card",
        isFullscreen ? "h-dvh rounded-none border-0" : "h-[calc(100dvh-12rem)] min-h-[480px]",
        className,
      )}
      onContextMenu={(e) => e.preventDefault()}
      onCopy={(e) => e.preventDefault()}
      onDragStart={(e) => e.preventDefault()}
    >
      {session.data && (
        <PdfToolbar
          title={session.data.resourceName}
          subtitle={session.data.courseName}
          page={page}
          pageCount={pageCount}
          zoomPercent={Math.round(scale * 100)}
          canZoomIn={scale < MAX_SCALE}
          canZoomOut={scale > MIN_SCALE}
          isFullscreen={isFullscreen}
          onPageChange={goTo}
          onZoomIn={() => zoom(ZOOM_STEP)}
          onZoomOut={() => zoom(-ZOOM_STEP)}
          onFit={fit}
          onToggleFullscreen={toggleFullscreen}
        />
      )}
      <div
        ref={viewportRef}
        tabIndex={0}
        onKeyDown={onKeyDown}
        aria-label="Document viewer. Use arrow keys to change page."
        className="relative flex-1 overflow-auto bg-muted/60 outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset dark:bg-muted/30"
      >
        {session.isLoading ? (
          <PdfLoading />
        ) : session.error ? (
          <PdfError error={session.error} onRetry={() => session.refetch()} />
        ) : session.data ? (
          <div className="flex min-h-full min-w-fit justify-center p-4">
            <PdfPage session={session.data} pageNumber={page} scale={scale} issuedAt={issuedAt} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
