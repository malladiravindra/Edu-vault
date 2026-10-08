"use client";

import Link from "next/link";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Skeleton } from "@/components/ui/skeleton";
import type { NotificationScope } from "@/lib/api/notificationApi";
import { useMarkAllNotificationsRead, useMarkNotificationRead, useNotifications, useUnreadNotificationCount } from "@/hooks/use-notifications";
import { NotificationItem } from "@/components/shared/notification-item";
import { EmptyState } from "@/components/shared/empty-state";

export function NotificationBell({ scope }: { scope: NotificationScope }) {
  const { data: unread = 0 } = useUnreadNotificationCount(scope);
  const list = useNotifications(scope, { pageSize: 5 });
  const markRead = useMarkNotificationRead(scope);
  const markAll = useMarkAllNotificationsRead(scope);

  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className="relative"
            aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
          />
        }
      >
        <Bell />
        {unread > 0 && (
          <span
            aria-hidden
            className="absolute top-1 right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[10px] leading-none font-semibold text-white"
          >
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[min(24rem,calc(100vw-2rem))] gap-0 p-0">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <p className="text-sm font-semibold">Notifications</p>
          <Button
            variant="ghost"
            size="xs"
            disabled={unread === 0 || markAll.isPending}
            onClick={() => markAll.mutate()}
          >
            Mark all as read
          </Button>
        </div>
        <div className="max-h-96 overflow-y-auto p-1.5">
          {list.isLoading ? (
            <div className="space-y-2 p-2">
              {Array.from({ length: 3 }, (_, i) => (
                <Skeleton key={i} className="h-14 w-full" />
              ))}
            </div>
          ) : list.data?.data.length ? (
            list.data.data.map((n) => (
              <NotificationItem key={n.id} notification={n} compact onMarkRead={(id) => markRead.mutate(id)} />
            ))
          ) : (
            <EmptyState compact title="No notifications" description="You're all caught up." />
          )}
        </div>
        <div className="border-t p-1.5">
          <Button variant="ghost" size="sm" className="w-full" nativeButton={false} render={<Link href={`/${scope}/notifications`} />}>
            View all notifications
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
