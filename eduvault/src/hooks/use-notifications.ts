"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ID, NotificationListParams, PaginatedResponse, Notification } from "@/types";
import { notificationApi, type NotificationScope } from "@/lib/api/notificationApi";
import { queryKeys } from "./query-keys";

export function useNotifications(scope: NotificationScope, params: NotificationListParams = {}) {
  return useQuery({
    queryKey: queryKeys.notifications.list(scope, params),
    queryFn: () => notificationApi.list(scope, params),
  });
}

export function useUnreadNotificationCount(scope: NotificationScope) {
  return useQuery({
    queryKey: queryKeys.notifications.unread(scope),
    queryFn: () => notificationApi.unreadCount(scope),
    refetchInterval: 60_000,
  });
}

export function useMarkNotificationRead(scope: NotificationScope) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: ID) => notificationApi.markRead(scope, id),
    // Optimistic: flip the item immediately in every cached list for this scope.
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: queryKeys.notifications.all(scope) });
      qc.setQueriesData<PaginatedResponse<Notification>>({ queryKey: [...queryKeys.notifications.all(scope), "list"] }, (old) =>
        old ? { ...old, data: old.data.map((n) => (n.id === id ? { ...n, read: true } : n)) } : old,
      );
    },
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.notifications.all(scope) }),
  });
}

export function useMarkAllNotificationsRead(scope: NotificationScope) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => notificationApi.markAllRead(scope),
    onSettled: () => qc.invalidateQueries({ queryKey: queryKeys.notifications.all(scope) }),
  });
}
