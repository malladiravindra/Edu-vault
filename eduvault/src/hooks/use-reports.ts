"use client";

import { keepPreviousData, useMutation, useQuery } from "@tanstack/react-query";
import type { ExportFormat, ReportFilters, ReportType } from "@/types";
import { reportApi } from "@/lib/api/reportApi";
import { queryKeys } from "./query-keys";

export function useAdminDashboard() {
  return useQuery({ queryKey: queryKeys.dashboard.admin, queryFn: () => reportApi.getAdminDashboard() });
}

export function useReport(type: ReportType, filters: ReportFilters = {}) {
  return useQuery({
    queryKey: queryKeys.reports.detail(type, filters),
    queryFn: () => reportApi.getReport(type, filters),
    placeholderData: keepPreviousData,
  });
}

export function useExportReport() {
  return useMutation({
    mutationFn: ({ type, format, filters }: { type: ReportType; format: ExportFormat; filters?: ReportFilters }) =>
      reportApi.exportReport(type, format, filters),
  });
}
