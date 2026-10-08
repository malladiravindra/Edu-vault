"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { ShieldX } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/shared/error-state";
import { EmptyState } from "@/components/shared/empty-state";
import { useCurrentUser } from "@/hooks/use-auth";
import type { UserRole } from "@/types";

/**
 * Client-side role check for rendering the right UI. This only prevents
 * showing the wrong portal; the backend enforces authorisation on every request.
 */
export function RoleGate({ role, children }: { role: UserRole; children: ReactNode }) {
  const { data: user, isLoading, error, refetch, isFetching } = useCurrentUser();

  if (isLoading) {
    return (
      <div className="flex min-h-dvh">
        <Skeleton className="hidden h-dvh w-64 rounded-none md:block" />
        <div className="flex-1 space-y-6 p-8">
          <Skeleton className="h-8 w-64" />
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex min-h-dvh items-center justify-center p-6">
        <ErrorState title="We couldn't verify your session" error={error} onRetry={() => refetch()} retrying={isFetching} />
      </div>
    );
  }

  if (!user || user.role !== role) {
    const home = user?.role === "admin" ? "/admin/dashboard" : user?.role === "student" ? "/student/dashboard" : "/login";
    return (
      <div className="flex min-h-dvh items-center justify-center p-6">
        <EmptyState
          icon={ShieldX}
          title="You don't have access to this area"
          description="This section is only available to a different account type."
          action={<Button nativeButton={false} render={<Link href={home} />}>{user ? "Go to my portal" : "Sign in"}</Button>}
        />
      </div>
    );
  }

  return <>{children}</>;
}
