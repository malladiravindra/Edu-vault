"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { DEFAULT_PAGE_SIZE } from "@/lib/constants";

export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}

type FilterValues = Record<string, string | undefined>;

/**
 * Local UI state for list pages: search (debounced), filters and pagination.
 * Changing search or a filter resets to page 1.
 *
 * const list = useListState({ status: undefined, courseId: undefined });
 * const query = useStudents(list.params);
 */
export function useListState<F extends FilterValues>(initialFilters: F, pageSize = DEFAULT_PAGE_SIZE) {
  const [search, setSearchRaw] = useState("");
  const [filters, setFilters] = useState<F>(initialFilters);
  const [page, setPage] = useState(1);
  const debouncedSearch = useDebouncedValue(search);

  const setSearch = useCallback((value: string) => {
    setSearchRaw(value);
    setPage(1);
  }, []);

  const setFilter = useCallback(<K extends keyof F>(key: K, value: F[K]) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  }, []);

  const reset = useCallback(() => {
    setSearchRaw("");
    setFilters(initialFilters);
    setPage(1);
    // initialFilters is intentionally captured once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hasActiveFilters = search !== "" || Object.values(filters).some((v) => v !== undefined && v !== "");

  const params = useMemo(
    () => ({ ...filters, search: debouncedSearch || undefined, page, pageSize }),
    [filters, debouncedSearch, page, pageSize],
  );

  return { search, setSearch, filters, setFilter, page, setPage, pageSize, params, reset, hasActiveFilters };
}
