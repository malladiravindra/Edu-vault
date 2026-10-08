"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ID, RegistrationListParams, RegistrationStatus } from "@/types";
import { registrationApi } from "@/lib/api/registrationApi";
import { queryKeys } from "./query-keys";

export function useRegistrations(params: RegistrationListParams = {}) {
  return useQuery({
    queryKey: queryKeys.registrations.list(params),
    queryFn: () => registrationApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useRegistration(id: ID | undefined) {
  return useQuery({
    queryKey: queryKeys.registrations.detail(id ?? ""),
    queryFn: () => registrationApi.get(id as ID),
    enabled: Boolean(id),
  });
}

export function useUpdateRegistrationStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, note }: { id: ID; status: RegistrationStatus; note?: string }) =>
      registrationApi.updateStatus(id, status, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.registrations.all });
      qc.invalidateQueries({ queryKey: queryKeys.access.all });
      qc.invalidateQueries({ queryKey: queryKeys.dashboard.admin });
    },
  });
}

export function useRequestAccess() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ courseId, message }: { courseId: ID; message?: string }) =>
      registrationApi.requestAccess(courseId, message),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.courses.all });
      qc.invalidateQueries({ queryKey: queryKeys.dashboard.student });
    },
  });
}
