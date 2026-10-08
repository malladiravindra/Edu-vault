"use client";

import { useState } from "react";
import { BellOff, CheckCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { NotificationType } from "@/types";
import type { NotificationScope } from "@/lib/api/notificationApi";
import { NOTIFICATION_TYPE_LABEL, toOptions } from "@/lib/constants";
import { notify } from "@/lib/toast";
import { useMarkAllNotificationsRead, useMarkNotificationRead, useNotifications } from "@/hooks/use-notifications";
import { EmptyState } from "./empty-state";
import { ErrorState } from "./error-state";
import { FilterDropdown } from "./filter-dropdown";
import { ListSkeleton } from "./loading-skeleton";
import { NotificationItem } from "./notification-item";

interface NotificationCenterProps {
  scope: NotificationScope;
  /** Restrict the type filter to types relevant for this portal. */
  types?: NotificationType[];
}

/** Full notification list with read filter, type filter and mark-all-read. */
export function NotificationCenter({ scope, types }: NotificationCenterProps) {
  const [readFilter, setReadFilter] = useState<"all" | "unread">("all");
  const [type, setType] = useState<NotificationType | undefined>();
  const query = useNotifications(scope, { read: readFilter === "unread" ? false : undefined, type, pageSize: 50 });
  const markRead = useMarkNotificationRead(scope);
  const markAll = useMarkAllNotificationsRead(scope);

  const typeOptions = toOptions(NOTIFICATION_TYPE_LABEL).filter((o) => !types || types.includes(o.value));
  const items = query.data?.data ?? [];
  const unreadInView = items.filter((n) => !n.read).length;

  return (
    <Card className="gap-0 py-0">
      <div className="flex flex-col gap-3 border-b p-4 sm:flex-row sm:items-center sm:justify-between">
        <Tabs value={readFilter} onValueChange={(v) => setReadFilter(v as "all" | "unread")}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="unread">Unread</TabsTrigger>
          </TabsList>
        </Tabs>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <FilterDropdown label="Type" allLabel="All types" value={type} onChange={setType} options={typeOptions} />
          <Button
            variant="outline"
            size="sm"
            className="h-9"
            disabled={unreadInView === 0 || markAll.isPending}
            onClick={() =>
              markAll.mutate(undefined, {
                onSuccess: () => notify.success("All notifications marked as read"),
                onError: (e) => notify.error(e, "Couldn't update notifications"),
              })
            }
          >
            <CheckCheck />
            Mark all as read
          </Button>
        </div>
      </div>
      <div className="p-2">
        {query.isLoading ? (
          <div className="p-2">
            <ListSkeleton />
          </div>
        ) : query.error ? (
          <ErrorState error={query.error} onRetry={() => query.refetch()} retrying={query.isFetching} />
        ) : items.length === 0 ? (
          <EmptyState
            icon={BellOff}
            title={readFilter === "unread" ? "You're all caught up" : "No notifications"}
            description={
              readFilter === "unread" ? "There are no unread notifications." : "Notifications about activity will appear here."
            }
          />
        ) : (
          <ul className="divide-y divide-border/60" aria-label="Notifications">
            {items.map((n) => (
              <li key={n.id} className="py-1">
                <NotificationItem notification={n} onMarkRead={(id) => markRead.mutate(id)} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
