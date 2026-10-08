"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ID, StudentListParams } from "@/types";
import { studentApi, type ChangePasswordInput, type ProfileUpdate } from "@/lib/api/studentApi";
import { queryKeys } from "./query-keys";

export function useStudents(params: StudentListParams = {}) {
  return useQuery({
    queryKey: queryKeys.students.list(params),
    queryFn: () => studentApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useStudent(id: ID | undefined) {
  return useQuery({
    queryKey: queryKeys.students.detail(id ?? ""),
    queryFn: () => studentApi.get(id as ID),
    enabled: Boolean(id),
  });
}

export function useStudentAccess(id: ID) {
  return useQuery({ queryKey: queryKeys.students.access(id), queryFn: () => studentApi.getAccess(id) });
}

export function useStudentPayments(id: ID) {
  return useQuery({ queryKey: queryKeys.students.payments(id), queryFn: () => studentApi.getPayments(id) });
}

export function useStudentActivity(id: ID) {
  return useQuery({ queryKey: queryKeys.students.activity(id), queryFn: () => studentApi.getActivity(id) });
}

export function useSuspendStudent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reason }: { id: ID; reason?: string }) => studentApi.suspend(id, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.students.all });
      qc.invalidateQueries({ queryKey: queryKeys.access.all });
    },
  });
}

export function useReinstateStudent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: ID) => studentApi.reinstate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.students.all });
      qc.invalidateQueries({ queryKey: queryKeys.access.all });
    },
  });
}

// Current student

export function useProfile() {
  return useQuery({ queryKey: queryKeys.students.profile, queryFn: () => studentApi.getProfile() });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ProfileUpdate) => studentApi.updateProfile(input),
    onSuccess: (data) => {
      qc.setQueryData(queryKeys.students.profile, data);
      qc.invalidateQueries({ queryKey: queryKeys.auth.me });
    },
  });
}

export function useChangePassword() {
  return useMutation({ mutationFn: (input: ChangePasswordInput) => studentApi.changePassword(input) });
}

export function useStudentDashboard() {
  return useQuery({ queryKey: queryKeys.dashboard.student, queryFn: () => studentApi.getDashboard() });
}
