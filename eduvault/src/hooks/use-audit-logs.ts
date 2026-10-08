"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { AuditLogListParams } from "@/types";
import { auditLogApi } from "@/lib/api/auditLogApi";
import { queryKeys } from "./query-keys";

export function useAuditLogs(params: AuditLogListParams = {}) {
  return useQuery({
    queryKey: queryKeys.auditLogs.list(params),
    queryFn: () => auditLogApi.list(params),
    placeholderData: keepPreviousData,
  });
}
