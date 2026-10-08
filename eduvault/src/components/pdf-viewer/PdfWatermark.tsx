"use client";

import { useMemo } from "react";
import type { ResourceViewerSession } from "@/types";

interface PdfWatermarkProps {
  watermark: ResourceViewerSession["watermark"];
  /** Timestamp shown in the corner stamp; identifies the viewing session. */
  issuedAt: string;
}

/**
 * Dynamic, tiled watermark rendered over each page. Text comes from the
 * server-issued viewer session so it identifies the viewer if a screenshot
 * leaks. This is a deterrent — in production the backend should also burn a
 * watermark into the rendered page images.
 */
export function PdfWatermark({ watermark, issuedAt }: PdfWatermarkProps) {
  const tile = useMemo(() => {
    const line1 = `${watermark.name} · ${watermark.email}`;
    const line2 = watermark.label;
    const esc = (s: string) => s.replace(/[<>&"']/g, (c) => `&#${c.charCodeAt(0)};`);
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="420" height="260">
      <g transform="rotate(-28 210 130)" font-family="Arial, sans-serif" fill="#0f172a" fill-opacity="0.09">
        <text x="210" y="122" text-anchor="middle" font-size="16" font-weight="600">${esc(line1)}</text>
        <text x="210" y="146" text-anchor="middle" font-size="12">${esc(line2)}</text>
      </g>
    </svg>`;
    return `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}")`;
  }, [watermark]);

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 select-none">
      <div className="absolute inset-0" style={{ backgroundImage: tile, backgroundRepeat: "repeat" }} />
      <div className="absolute right-3 bottom-3 rounded bg-slate-900/70 px-2 py-1 font-mono text-[10px] leading-tight text-white/90">
        {watermark.email}
        <br />
        {issuedAt}
      </div>
    </div>
  );
}
