"use client";

import type { ReactNode } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { PaginatedResponse } from "@/types";
import { cn } from "@/lib/utils";
import { EmptyState } from "./empty-state";
import { ErrorState } from "./error-state";
import { TableSkeleton } from "./loading-skeleton";
import { Pagination } from "./pagination";
import type { LucideIcon } from "lucide-react";

export interface DataTableColumn<T> {
  id: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
  headerClassName?: string;
  /**
   * Hide the column below a breakpoint to keep tables readable on small
   * screens. The table also scrolls horizontally as a fallback.
   */
  hideBelow?: "sm" | "md" | "lg" | "xl";
  align?: "left" | "right" | "center";
}

const HIDE_CLASS: Record<NonNullable<DataTableColumn<unknown>["hideBelow"]>, string> = {
  sm: "hidden sm:table-cell",
  md: "hidden md:table-cell",
  lg: "hidden lg:table-cell",
  xl: "hidden xl:table-cell",
};

interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  /** Either a plain array or a paginated response. */
  data: T[] | PaginatedResponse<T> | undefined;
  getRowId: (row: T) => string;
  isLoading?: boolean;
  isFetching?: boolean;
  error?: unknown;
  onRetry?: () => void;
  onRowClick?: (row: T) => void;
  onPageChange?: (page: number) => void;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyIcon?: LucideIcon;
  emptyAction?: ReactNode;
  itemLabel?: string;
  caption?: string;
  className?: string;
}

/** Ignore row clicks that originate from buttons, links or menus inside the row. */
function isFromInteractive(e: React.MouseEvent<HTMLElement>) {
  const target = e.target as HTMLElement;
  // React bubbles events from portals (menus, dialogs) through the row even though they're outside it in the DOM.
  if (!e.currentTarget.contains(target)) return true;
  return Boolean(target.closest("button, a, input, select, textarea, [role=menuitem], [role=checkbox]"));
}

function isPaginated<T>(data: DataTableProps<T>["data"]): data is PaginatedResponse<T> {
  return Boolean(data && !Array.isArray(data));
}

export function DataTable<T>({
  columns,
  data,
  getRowId,
  isLoading,
  isFetching,
  error,
  onRetry,
  onRowClick,
  onPageChange,
  emptyTitle = "No results found",
  emptyDescription = "Try adjusting your search or filters.",
  emptyIcon,
  emptyAction,
  itemLabel,
  caption,
  className,
}: DataTableProps<T>) {
  const rows = isPaginated(data) ? data.data : (data ?? []);
  const alignClass = (a?: DataTableColumn<T>["align"]) =>
    a === "right" ? "text-right" : a === "center" ? "text-center" : undefined;

  let body: ReactNode;
  if (isLoading) {
    body = <TableSkeleton columns={Math.min(columns.length, 6)} />;
  } else if (error) {
    body = <ErrorState error={error} onRetry={onRetry} retrying={isFetching} />;
  } else if (rows.length === 0) {
    body = <EmptyState title={emptyTitle} description={emptyDescription} icon={emptyIcon} action={emptyAction} />;
  }

  return (
    <div className={cn("overflow-hidden rounded-xl border bg-card", className)}>
      {body ?? (
        <div className={cn("transition-opacity", isFetching && "opacity-60")}>
          <Table>
            {caption && <caption className="sr-only">{caption}</caption>}
            <TableHeader className="bg-muted/40">
              <TableRow className="hover:bg-transparent">
                {columns.map((col) => (
                  <TableHead
                    key={col.id}
                    scope="col"
                    className={cn(
                      "h-10 px-4 text-xs font-medium tracking-wide text-muted-foreground uppercase",
                      col.hideBelow && HIDE_CLASS[col.hideBelow],
                      alignClass(col.align),
                      col.headerClassName,
                    )}
                  >
                    {col.header}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow
                  key={getRowId(row)}
                  onClick={onRowClick ? (e) => !isFromInteractive(e) && onRowClick(row) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) {
                            e.preventDefault();
                            onRowClick(row);
                          }
                        }
                      : undefined
                  }
                  tabIndex={onRowClick ? 0 : undefined}
                  className={cn(
                    onRowClick &&
                      "cursor-pointer focus-visible:bg-muted/60 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring",
                  )}
                >
                  {columns.map((col) => (
                    <TableCell
                      key={col.id}
                      className={cn(
                        "px-4 py-3",
                        col.hideBelow && HIDE_CLASS[col.hideBelow],
                        alignClass(col.align),
                        col.className,
                      )}
                    >
                      {col.cell(row)}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
      {isPaginated(data) && onPageChange && !isLoading && !error && rows.length > 0 && (
        <div className="border-t px-4 py-3">
          <Pagination
            page={data.page}
            totalPages={data.totalPages}
            total={data.total}
            pageSize={data.pageSize}
            onPageChange={onPageChange}
            itemLabel={itemLabel}
          />
        </div>
      )}
    </div>
  );
}

/** Toolbar row above a table: search on the left, filters/actions wrap on small screens. */
export function DataTableToolbar({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center", className)}>{children}</div>;
}
