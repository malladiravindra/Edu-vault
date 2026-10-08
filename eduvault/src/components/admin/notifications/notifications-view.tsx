import Link from "next/link";
import { Settings } from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { NotificationCenter } from "@/components/shared/notification-center";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export function AdminNotificationsView() {
  return (
    <div className="space-y-6">
      <PageHeader title="Notifications" description="Platform activity that needs your attention." />
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="min-w-0">
          <NotificationCenter scope="admin" />
        </div>
        <aside className="hidden xl:block">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                <h2>Notification preferences</h2>
              </CardTitle>
              <CardDescription>Choose which platform events send you email alerts.</CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="outline" size="sm" nativeButton={false} render={<Link href="/admin/settings" />}>
                <Settings aria-hidden />
                Manage preferences
              </Button>
            </CardContent>
          </Card>
        </aside>
      </div>
    </div>
  );
}
