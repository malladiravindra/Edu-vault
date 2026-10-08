"use client";

import Link from "next/link";
import { ChevronsUpDown, LogOut, Moon, Settings, Sun, UserRound } from "lucide-react";
import { useTheme } from "next-themes";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Skeleton } from "@/components/ui/skeleton";
import { UserAvatar } from "@/components/shared/user-avatar";
import { useCurrentUser, useLogout } from "@/hooks/use-auth";
import type { UserRole } from "@/types";

export function UserMenu({ role }: { role: UserRole }) {
  const { data: user, isLoading } = useCurrentUser();
  const logout = useLogout();
  const { resolvedTheme, setTheme } = useTheme();

  if (isLoading || !user) {
    return <Skeleton className="size-9 rounded-full" />;
  }

  const accountHref = role === "admin" ? "/admin/settings" : "/student/profile";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="flex items-center gap-2 rounded-lg p-1 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring"
        aria-label="Open account menu"
      >
        <UserAvatar name={user.name} src={user.avatarUrl} size="sm" />
        <span className="hidden min-w-0 2xl:block">
          <span className="block max-w-36 truncate text-sm font-medium">{user.name}</span>
          <span className="block text-xs text-muted-foreground capitalize">{user.role}</span>
        </span>
        <ChevronsUpDown className="hidden size-3.5 text-muted-foreground 2xl:block" aria-hidden />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuGroup>
          <DropdownMenuLabel className="font-normal">
            <span className="block truncate text-sm font-medium text-foreground">{user.name}</span>
            <span className="block truncate text-xs">{user.email}</span>
          </DropdownMenuLabel>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuGroup>
          <DropdownMenuItem render={<Link href={accountHref} />}>
            {role === "admin" ? <Settings /> : <UserRound />}
            {role === "admin" ? "Settings" : "Profile"}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}>
            {resolvedTheme === "dark" ? <Sun /> : <Moon />}
            {resolvedTheme === "dark" ? "Light mode" : "Dark mode"}
          </DropdownMenuItem>
        </DropdownMenuGroup>
        <DropdownMenuSeparator />
        <DropdownMenuItem variant="destructive" onClick={() => logout.mutate()} disabled={logout.isPending}>
          <LogOut />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
