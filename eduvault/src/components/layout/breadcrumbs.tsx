"use client";

import { createContext, Fragment, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { SEGMENT_LABELS, isRoutablePath } from "@/lib/navigation";

type LabelMap = Record<string, string>;

const BreadcrumbContext = createContext<{
  labels: LabelMap;
  setLabel: (segment: string, label: string | undefined) => void;
} | null>(null);

export function BreadcrumbProvider({ children }: { children: ReactNode }) {
  const [labels, setLabels] = useState<LabelMap>({});
  const setLabel = useCallback((segment: string, label: string | undefined) => {
    setLabels((prev) => {
      if (prev[segment] === label) return prev;
      const next = { ...prev };
      if (label === undefined) delete next[segment];
      else next[segment] = label;
      return next;
    });
  }, []);
  const value = useMemo(() => ({ labels, setLabel }), [labels, setLabel]);
  return <BreadcrumbContext.Provider value={value}>{children}</BreadcrumbContext.Provider>;
}

/**
 * Lets a detail page replace a dynamic segment (e.g. an ID) with a readable
 * label in the header breadcrumbs:  useBreadcrumbLabel(id, student?.name)
 */
export function useBreadcrumbLabel(segment: string | undefined, label: string | undefined) {
  const ctx = useContext(BreadcrumbContext);
  const setLabel = ctx?.setLabel;
  useEffect(() => {
    if (!segment || !setLabel) return;
    setLabel(segment, label);
    return () => setLabel(segment, undefined);
  }, [segment, label, setLabel]);
}

function humanize(segment: string) {
  return segment.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function AppBreadcrumbs() {
  const pathname = usePathname();
  const labels = useContext(BreadcrumbContext)?.labels ?? {};
  const segments = pathname.split("/").filter(Boolean);
  // Skip the portal root ("admin"/"student") — the navbar brand already shows it.
  const crumbs = segments.slice(1).map((segment, i) => ({
    href: `/${segments.slice(0, i + 2).join("/")}`,
    label: labels[segment] ?? SEGMENT_LABELS[segment] ?? (/\d/.test(segment) ? "Details" : humanize(segment)),
  }));

  // A top-level page's only crumb would just repeat its page title.
  if (crumbs.length < 2) return null;

  return (
    <Breadcrumb>
      <BreadcrumbList>
        {crumbs.map((crumb, i) => {
          const last = i === crumbs.length - 1;
          return (
            <Fragment key={crumb.href}>
              <BreadcrumbItem className={!last ? "hidden md:inline-flex" : undefined}>
                {last ? (
                  <BreadcrumbPage className="max-w-48 truncate sm:max-w-80">{crumb.label}</BreadcrumbPage>
                ) : !isRoutablePath(crumb.href) ? (
                  <span>{crumb.label}</span>
                ) : (
                  <BreadcrumbLink render={<Link href={crumb.href} />}>{crumb.label}</BreadcrumbLink>
                )}
              </BreadcrumbItem>
              {!last && <BreadcrumbSeparator className="hidden md:block" />}
            </Fragment>
          );
        })}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
