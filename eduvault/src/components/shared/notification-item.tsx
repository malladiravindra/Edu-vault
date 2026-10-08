"use client";

import Link from "next/link";
import {
  Bell,
  BookOpen,
  CreditCard,
  FileText,
  KeyRound,
  ShieldAlert,
  UserPlus,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { Notification, NotificationType } from "@/types";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

const TYPE_ICON: Record<NotificationType, LucideIcon> = {
  registration: UserPlus,
  access: KeyRound,
  payment: CreditCard,
  course: BookOpen,
  resource: FileText,
  system: Bell,
  security: ShieldAlert,
};

interface NotificationItemProps {
  notification: Notification;
  onMarkRead?: (id: string) => void;
  compact?: boolean;
}

export function NotificationItem({ notification: n, onMarkRead, compact }: NotificationItemProps) {
  const Icon = TYPE_ICON[n.type];
  const content = (
    <>
      <div
        className={cn(
          "flex shrink-0 items-center justify-center rounded-full",
          compact ? "size-8" : "size-9",
          n.type === "security" ? "bg-destructive/10 text-destructive" : "bg-primary/10 text-primary",
        )}
      >
        <Icon className="size-4" aria-hidden />
      </div>
      <div className="min-w-0 flex-1 space-y-0.5">
        <p className={cn("text-sm", !n.read ? "font-semibold" : "font-medium")}>
          {n.title}
          {!n.read && <span className="sr-only"> (unread)</span>}
        </p>
        <p className={cn("text-sm text-muted-foreground", compact && "line-clamp-2")}>{n.description}</p>
        <p className="text-xs text-muted-foreground">{formatRelative(n.createdAt)}</p>
      </div>
    </>
  );

  return (
    <div
      className={cn(
        "group relative flex gap-3 rounded-lg p-3 transition-colors",
        !n.read && "bg-primary/[0.04]",
        n.href && "hover:bg-muted/60",
      )}
    >
      {!n.read && <span aria-hidden className="absolute top-4 left-1 size-1.5 rounded-full bg-primary" />}
      {n.href ? (
        <Link
          href={n.href}
          onClick={() => !n.read && onMarkRead?.(n.id)}
          className="flex min-w-0 flex-1 gap-3 rounded focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
          {content}
        </Link>
      ) : (
        <div className="flex min-w-0 flex-1 gap-3">{content}</div>
      )}
      {!n.read && onMarkRead && !compact && (
        <Button
          variant="ghost"
          size="sm"
          className="shrink-0 self-start text-xs"
          onClick={() => onMarkRead(n.id)}
        >
          Mark as read
        </Button>
      )}
    </div>
  );
}
