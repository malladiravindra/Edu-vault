"use client";

import type { ResourceViewerSession } from "@/types";
import { useResourcePage } from "@/hooks/use-resources";
import { PdfPageSkeleton } from "./PdfLoading";
import { PdfWatermark } from "./PdfWatermark";
import { PdfError } from "./PdfError";

/** Native page size the backend renders at (US Letter @ 96dpi). */
export const PAGE_BASE_WIDTH = 816;
export const PAGE_BASE_HEIGHT = 1056;

interface PdfPageProps {
  session: ResourceViewerSession;
  pageNumber: number;
  scale: number;
  issuedAt: string;
}

/**
 * Renders one server-rendered page image with the watermark overlay.
 * The image is fetched per page from the API — there is no PDF URL to download.
 */
export function PdfPage({ session, pageNumber, scale, issuedAt }: PdfPageProps) {
  const page = useResourcePage(session.resourceId, pageNumber);
  const width = Math.round((page.data?.width ?? PAGE_BASE_WIDTH) * scale);
  const height = Math.round((page.data?.height ?? PAGE_BASE_HEIGHT) * scale);

  if (page.error) {
    return (
      <div className="bg-card shadow-sm" style={{ width, height }}>
        <PdfError error={page.error} onRetry={() => page.refetch()} />
      </div>
    );
  }

  if (page.isLoading || !page.data) {
    return <PdfPageSkeleton width={width} height={height} />;
  }

  return (
    <div
      className="relative bg-white shadow-md ring-1 ring-black/5"
      style={{ width, height }}
      aria-label={`Page ${pageNumber} of ${session.pageCount}`}
      role="img"
    >
      {page.data.imageSrc && (
        // eslint-disable-next-line @next/next/no-img-element -- short-lived, session-bound page image; must not be optimised/cached by next/image
        <img
          src={page.data.imageSrc}
          alt=""
          width={width}
          height={height}
          draggable={false}
          className="pointer-events-none block h-full w-full select-none"
        />
      )}
      <PdfWatermark watermark={session.watermark} issuedAt={issuedAt} />
    </div>
  );
}
