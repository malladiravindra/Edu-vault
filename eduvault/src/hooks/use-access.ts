"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AccessListParams, ID } from "@/types";
import { accessApi } from "@/lib/api/accessApi";
import { queryKeys } from "./query-keys";

export function useAccessRecords(params: AccessListParams = {}) {
  return useQuery({
    queryKey: queryKeys.access.list(params),
    queryFn: () => accessApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useAccessSummary() {
  return useQuery({ queryKey: queryKeys.access.summary, queryFn: () => accessApi.summary() });
}

export function useUpdateAccessStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: ID; status: "active" | "suspended" }) => accessApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.access.all }),
  });
}

export function useExtendAccess() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, days }: { id: ID; days: number }) => accessApi.extend(id, days),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.access.all }),
  });
}
