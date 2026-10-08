"use client";

import { useState } from "react";
import { LogOut, ShieldCheck, ShieldOff } from "lucide-react";
import type { Student } from "@/types";
import { notify } from "@/lib/toast";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Modal } from "@/components/shared/modal";
import { ConfirmationDialog } from "@/components/shared/confirmation-dialog";
import { ChangePasswordForm } from "./change-password-form";

export function SecurityCard({ profile }: { profile: Student }) {
  const [twoFactorOpen, setTwoFactorOpen] = useState(false);
  const [signOutOpen, setSignOutOpen] = useState(false);
  const enabled = profile.twoFactorEnabled;

  return (
    <Card>
      <CardHeader>
        <CardTitle>
          <h2>Security</h2>
        </CardTitle>
        <CardDescription>Keep your account secure with a strong password and two-factor authentication.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <section aria-labelledby="change-password-heading" className="space-y-4">
          <h3 id="change-password-heading" className="text-sm font-medium">
            Change password
          </h3>
          <ChangePasswordForm />
        </section>

        <Separator />

        <section
          aria-labelledby="two-factor-heading"
          className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex items-start gap-3">
            <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
              {enabled ? <ShieldCheck className="size-4.5" aria-hidden /> : <ShieldOff className="size-4.5" aria-hidden />}
            </div>
            <div className="space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h3 id="two-factor-heading" className="text-sm font-medium">
                  Two-factor authentication
                </h3>
                <Badge variant={enabled ? "default" : "outline"}>{enabled ? "Enabled" : "Disabled"}</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                {enabled
                  ? "A verification code is required each time you sign in."
                  : "Add an extra layer of protection with a verification code at sign-in."}
              </p>
            </div>
          </div>
          <Button variant="outline" size="sm" onClick={() => setTwoFactorOpen(true)} className="self-start sm:self-center">
            Manage
          </Button>
        </section>

        <Separator />

        <section
          aria-labelledby="sessions-heading"
          className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="space-y-1">
            <h3 id="sessions-heading" className="text-sm font-medium">
              Other sessions
            </h3>
            <p className="text-sm text-muted-foreground">
              Sign out everywhere else if you used a shared device or suspect unusual activity.
            </p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setSignOutOpen(true)} className="self-start sm:self-center">
            <LogOut />
            Sign out of other sessions
          </Button>
        </section>
      </CardContent>

      <Modal
        open={twoFactorOpen}
        onOpenChange={setTwoFactorOpen}
        title="Two-factor authentication"
        description={
          enabled
            ? "Two-factor authentication is currently enabled on your account."
            : "Two-factor authentication is currently disabled on your account."
        }
        footer={<Button onClick={() => setTwoFactorOpen(false)}>Got it</Button>}
      >
        <div className="space-y-3 text-sm">
          <p className="text-muted-foreground">How it works:</p>
          <ol className="list-decimal space-y-1.5 pl-5">
            <li>Install an authenticator app on your phone.</li>
            <li>Scan the QR code we show you to link it to your EduVault account.</li>
            <li>Enter the 6-digit code from the app to confirm setup.</li>
            <li>From then on, you&apos;ll enter a fresh code each time you sign in.</li>
          </ol>
          <p className="rounded-lg border bg-muted/40 p-3 text-muted-foreground">
            Two-factor setup will be available once connected to the authentication service.
          </p>
        </div>
      </Modal>

      <ConfirmationDialog
        open={signOutOpen}
        onOpenChange={setSignOutOpen}
        title="Sign out of other sessions?"
        description="You'll stay signed in on this device. Every other browser and device will need to sign in again."
        confirmLabel="Sign out other sessions"
        destructive
        onConfirm={() => {
          setSignOutOpen(false);
          notify.success("Signed out of other sessions", "You're still signed in on this device.");
        }}
      />
    </Card>
  );
}
