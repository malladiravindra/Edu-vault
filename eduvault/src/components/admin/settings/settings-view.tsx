"use client";

import { useState, useSyncExternalStore, type ReactNode } from "react";
import { Bell, KeyRound, Settings2, ShieldCheck, UserRound } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useSettings } from "@/hooks/use-settings";
import { useCurrentUser } from "@/hooks/use-auth";
import { PageHeader } from "@/components/shared/page-header";
import { ErrorState } from "@/components/shared/error-state";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ProfileSettings } from "./profile-settings";
import { PlatformSettingsForm } from "./platform-settings-form";
import { NotificationSettingsForm } from "./notification-settings-form";
import { AccessDefaultsForm } from "./access-defaults-form";
import { SecuritySettingsForm } from "./security-settings-form";
import { ChangePasswordCard } from "./change-password-card";

type Section = "profile" | "platform" | "notifications" | "access" | "security";

const SECTIONS: { value: Section; label: string; icon: LucideIcon }[] = [
  { value: "profile", label: "Profile", icon: UserRound },
  { value: "platform", label: "Platform Settings", icon: Settings2 },
  { value: "notifications", label: "Notification Preferences", icon: Bell },
  { value: "access", label: "Access Defaults", icon: KeyRound },
  { value: "security", label: "Security", icon: ShieldCheck },
];

const LG_QUERY = "(min-width: 1024px)";

function subscribe(callback: () => void) {
  const mql = window.matchMedia(LG_QUERY);
  mql.addEventListener("change", callback);
  return () => mql.removeEventListener("change", callback);
}

function useIsLargeScreen() {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(LG_QUERY).matches,
    () => false,
  );
}

function SectionSkeleton() {
  return (
    <Card aria-busy="true" aria-label="Loading settings">
      <CardHeader className="space-y-2 border-b">
        <Skeleton className="h-5 w-40" />
        <Skeleton className="h-4 w-64" />
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="grid gap-4 sm:grid-cols-2">
          {Array.from({ length: 4 }, (_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-8 w-full" />
            </div>
          ))}
        </div>
        {Array.from({ length: 2 }, (_, i) => (
          <div key={i} className="flex items-center justify-between gap-4">
            <div className="space-y-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-3 w-72 max-w-full" />
            </div>
            <Skeleton className="h-5 w-8 rounded-full" />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

/** Renders loading / error states for a query, then the section content. */
function QueryGate<T>({
  query,
  children,
}: {
  query: { data: T | undefined; isLoading: boolean; error: unknown; isFetching: boolean; refetch: () => unknown };
  children: (data: T) => ReactNode;
}) {
  if (query.data !== undefined) return <>{children(query.data)}</>;
  if (query.error) {
    return (
      <Card>
        <ErrorState
          error={query.error}
          title="We couldn't load your settings"
          onRetry={() => query.refetch()}
          retrying={query.isFetching}
        />
      </Card>
    );
  }
  return <SectionSkeleton />;
}

export function SettingsView() {
  const [section, setSection] = useState<Section>("profile");
  const isLarge = useIsLargeScreen();
  const settings = useSettings();
  const user = useCurrentUser();

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" description="Manage your profile and platform-wide configuration." />

      <Tabs
        value={section}
        onValueChange={(v) => setSection(v as Section)}
        orientation={isLarge ? "vertical" : "horizontal"}
        className="gap-6 lg:flex-row lg:items-start"
      >
        <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0 lg:sticky lg:top-20 lg:w-60 lg:shrink-0 lg:overflow-visible">
          <TabsList
            variant={isLarge ? "default" : "line"}
            aria-label="Settings sections"
            className="w-max lg:h-fit lg:w-full lg:items-stretch lg:gap-0.5 lg:bg-transparent lg:p-0"
          >
            {SECTIONS.map((s) => (
              <TabsTrigger
                key={s.value}
                value={s.value}
                className="px-3 lg:h-9 lg:flex-none lg:after:hidden lg:data-active:bg-muted lg:data-active:shadow-none"
              >
                <s.icon aria-hidden />
                {s.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>

        <div className="min-w-0 flex-1">
          <TabsContent value="profile">
            <QueryGate query={user}>{(u) => <ProfileSettings user={u} />}</QueryGate>
          </TabsContent>
          <TabsContent value="platform">
            <QueryGate query={settings}>{(s) => <PlatformSettingsForm settings={s.platform} />}</QueryGate>
          </TabsContent>
          <TabsContent value="notifications">
            <QueryGate query={settings}>{(s) => <NotificationSettingsForm settings={s.notifications} />}</QueryGate>
          </TabsContent>
          <TabsContent value="access">
            <QueryGate query={settings}>{(s) => <AccessDefaultsForm settings={s.accessDefaults} />}</QueryGate>
          </TabsContent>
          <TabsContent value="security" className="space-y-6">
            <QueryGate query={settings}>{(s) => <SecuritySettingsForm settings={s.security} />}</QueryGate>
            <ChangePasswordCard />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
