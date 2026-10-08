"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ID, LearningHistoryParams } from "@/types";
import { learningApi } from "@/lib/api/learningApi";
import { queryKeys } from "./query-keys";

export function useLearningHistory(params: LearningHistoryParams = {}) {
  return useQuery({
    queryKey: queryKeys.learning.history(params),
    queryFn: () => learningApi.history(params),
    placeholderData: keepPreviousData,
  });
}

export function useRecentLearning(limit = 4) {
  return useQuery({ queryKey: queryKeys.learning.recent(limit), queryFn: () => learningApi.recent(limit) });
}

export function useRecordProgress() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ resourceId, page, secondsSpent }: { resourceId: ID; page: number; secondsSpent: number }) =>
      learningApi.recordProgress(resourceId, page, secondsSpent),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.learning.all }),
  });
}
