"use client";

import type { ReactNode } from "react";
import { useProfile } from "@/hooks/use-students";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorState } from "@/components/shared/error-state";
import { ProfileSummaryCard } from "./profile-summary-card";
import { ProfileInfoForm } from "./profile-info-form";
import { AccountInfoCard } from "./account-info-card";
import { SecurityCard } from "./security-card";

function ProfileSkeleton() {
  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]" aria-busy="true" aria-label="Loading profile">
      <Card className="self-start">
        <CardContent className="flex flex-col items-center gap-3 pt-2">
          <Skeleton className="size-20 rounded-full" />
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-5 w-16 rounded-full" />
          <div className="w-full space-y-3 pt-4">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-4 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
      <div className="space-y-6">
        {[4, 5, 6].map((lines) => (
          <Card key={lines}>
            <CardContent className="space-y-4">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-72 max-w-full" />
              {Array.from({ length: lines - 2 }, (_, i) => (
                <Skeleton key={i} className="h-9 w-full" />
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export function ProfileView() {
  const query = useProfile();
  const profile = query.data;

  let body: ReactNode;
  if (query.isLoading) {
    body = <ProfileSkeleton />;
  } else if (query.error || !profile) {
    body = (
      <Card className="py-0">
        <ErrorState
          title="We couldn't load your profile"
          error={query.error}
          onRetry={() => query.refetch()}
          retrying={query.isFetching}
        />
      </Card>
    );
  } else {
    body = (
      <div className="grid gap-6 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
        <div className="lg:sticky lg:top-20 lg:self-start">
          <ProfileSummaryCard profile={profile} />
        </div>
        <div className="space-y-6">
          <ProfileInfoForm profile={profile} />
          <AccountInfoCard profile={profile} />
          <SecurityCard profile={profile} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Profile" description="Manage your personal information and account security" />
      {body}
    </div>
  );
}
