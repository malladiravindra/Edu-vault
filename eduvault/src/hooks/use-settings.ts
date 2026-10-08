"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AdminSettings } from "@/types";
import { settingsApi, type SettingsSection } from "@/lib/api/settingsApi";
import { queryKeys } from "./query-keys";

export function useSettings() {
  return useQuery({ queryKey: queryKeys.settings, queryFn: () => settingsApi.get() });
}

export function useUpdateSettings<K extends SettingsSection>(section: K) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (values: AdminSettings[K]) => settingsApi.update(section, values),
    onSuccess: (data) => qc.setQueryData(queryKeys.settings, data),
  });
}
