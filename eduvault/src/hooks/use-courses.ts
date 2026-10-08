"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { CourseInput, CourseListParams, CourseStatus, ID } from "@/types";
import { courseApi, type StudentCatalogParams } from "@/lib/api/courseApi";
import { queryKeys } from "./query-keys";

export function useCourses(params: CourseListParams = {}) {
  return useQuery({
    queryKey: queryKeys.courses.list(params),
    queryFn: () => courseApi.list(params),
    placeholderData: keepPreviousData,
  });
}

export function useCourse(id: ID | undefined) {
  return useQuery({
    queryKey: queryKeys.courses.detail(id ?? ""),
    queryFn: () => courseApi.get(id as ID),
    enabled: Boolean(id),
  });
}

export function useCourseCategories() {
  return useQuery({ queryKey: queryKeys.courses.categories, queryFn: () => courseApi.listCategories(), staleTime: Infinity });
}

export function useCreateCourse() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CourseInput) => courseApi.create(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.courses.all }),
  });
}

export function useUpdateCourse(id: ID) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Partial<CourseInput>) => courseApi.update(id, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.courses.all }),
  });
}

export function useSetCourseStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: ID; status: CourseStatus }) => courseApi.setStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.courses.all }),
  });
}

// Student-facing

export function useCourseCatalog(params: StudentCatalogParams = {}) {
  return useQuery({
    queryKey: queryKeys.courses.catalog(params),
    queryFn: () => courseApi.catalog(params),
    placeholderData: keepPreviousData,
  });
}

export function useStudentCourse(id: ID | undefined) {
  return useQuery({
    queryKey: queryKeys.courses.studentDetail(id ?? ""),
    queryFn: () => courseApi.getForStudent(id as ID),
    enabled: Boolean(id),
  });
}

export function useMyCourses() {
  return useQuery({ queryKey: queryKeys.courses.mine, queryFn: () => courseApi.myCourses() });
}
