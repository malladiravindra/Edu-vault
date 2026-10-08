"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ID, ResourceStatus } from "@/types";
import { resourceApi, type ResourceUploadInput } from "@/lib/api/resourceApi";
import { queryKeys } from "./query-keys";

export function useCourseResources(courseId: ID) {
  return useQuery({ queryKey: queryKeys.resources.byCourse(courseId), queryFn: () => resourceApi.listByCourse(courseId) });
}

export function usePublishedResources(courseId: ID | undefined) {
  return useQuery({
    queryKey: queryKeys.resources.published(courseId ?? ""),
    queryFn: () => resourceApi.listPublishedByCourse(courseId as ID),
    enabled: Boolean(courseId),
  });
}

function useInvalidateResources() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: queryKeys.resources.all });
    qc.invalidateQueries({ queryKey: queryKeys.courses.all });
  };
}

export function useUploadResource(courseId: ID) {
  const invalidate = useInvalidateResources();
  return useMutation({
    mutationFn: ({ input, onProgress }: { input: ResourceUploadInput; onProgress?: (p: number) => void }) =>
      resourceApi.upload(courseId, input, onProgress),
    onSuccess: invalidate,
  });
}

export function useReplaceResource() {
  const invalidate = useInvalidateResources();
  return useMutation({
    mutationFn: ({ id, file, onProgress }: { id: ID; file: File; onProgress?: (p: number) => void }) =>
      resourceApi.replace(id, file, onProgress),
    onSuccess: invalidate,
  });
}

export function useSetResourceStatus() {
  const invalidate = useInvalidateResources();
  return useMutation({
    mutationFn: ({ id, status }: { id: ID; status: Exclude<ResourceStatus, "processing"> }) =>
      resourceApi.setStatus(id, status),
    onSuccess: invalidate,
  });
}

export function useDeleteResource() {
  const invalidate = useInvalidateResources();
  return useMutation({ mutationFn: (id: ID) => resourceApi.remove(id), onSuccess: invalidate });
}

/** Viewer session; never cached long since it carries short-lived authorisation. */
export function useViewerSession(resourceId: ID | undefined, mode: "student" | "admin-preview" = "student") {
  return useQuery({
    queryKey: queryKeys.resources.session(resourceId ?? "", mode),
    queryFn: () => resourceApi.openViewerSession(resourceId as ID, mode),
    enabled: Boolean(resourceId),
    staleTime: 0,
    gcTime: 0,
    retry: false,
  });
}

export function useResourcePage(resourceId: ID | undefined, page: number, enabled = true) {
  return useQuery({
    queryKey: queryKeys.resources.page(resourceId ?? "", page),
    queryFn: () => resourceApi.getPage(resourceId as ID, page),
    enabled: Boolean(resourceId) && enabled,
    staleTime: 60_000,
    gcTime: 60_000,
  });
}
