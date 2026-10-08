"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PaginationProps {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  className?: string;
  itemLabel?: string;
}

function pageWindow(page: number, totalPages: number): (number | "…")[] {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
  const pages: (number | "…")[] = [1];
  const start = Math.max(2, page - 1);
  const end = Math.min(totalPages - 1, page + 1);
  if (start > 2) pages.push("…");
  for (let p = start; p <= end; p++) pages.push(p);
  if (end < totalPages - 1) pages.push("…");
  pages.push(totalPages);
  return pages;
}

export function Pagination({ page, totalPages, total, pageSize, onPageChange, className, itemLabel = "results" }: PaginationProps) {
  if (total === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <nav
      aria-label="Pagination"
      className={cn("flex flex-col items-center justify-between gap-3 sm:flex-row", className)}
    >
      <p className="text-sm text-muted-foreground" aria-live="polite">
        Showing <span className="font-medium text-foreground">{from}</span>–
        <span className="font-medium text-foreground">{to}</span> of{" "}
        <span className="font-medium text-foreground">{total}</span> {itemLabel}
      </p>
      {totalPages > 1 && (
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page - 1)}
            disabled={page <= 1}
            aria-label="Previous page"
          >
            <ChevronLeft />
            <span className="hidden sm:inline">Previous</span>
          </Button>
          <div className="hidden items-center gap-1 sm:flex">
            {pageWindow(page, totalPages).map((p, i) =>
              p === "…" ? (
                <span key={`gap-${i}`} className="px-1.5 text-sm text-muted-foreground" aria-hidden>
                  …
                </span>
              ) : (
                <Button
                  key={p}
                  variant={p === page ? "secondary" : "ghost"}
                  size="icon-sm"
                  onClick={() => onPageChange(p)}
                  aria-label={`Page ${p}`}
                  aria-current={p === page ? "page" : undefined}
                  className={cn(p === page && "font-semibold")}
                >
                  {p}
                </Button>
              ),
            )}
          </div>
          <span className="px-2 text-sm text-muted-foreground sm:hidden">
            {page} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onPageChange(page + 1)}
            disabled={page >= totalPages}
            aria-label="Next page"
          >
            <span className="hidden sm:inline">Next</span>
            <ChevronRight />
          </Button>
        </div>
      )}
    </nav>
  );
}
