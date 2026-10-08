"use client";

import { useState } from "react";
import { addDays } from "date-fns";
import { Loader2 } from "lucide-react";
import type { AccessRecord } from "@/types";
import { formatDate } from "@/lib/format";
import { notify } from "@/lib/toast";
import { useExtendAccess } from "@/hooks/use-access";
import { Modal } from "@/components/shared/modal";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const EXTENSION_OPTIONS = [
  { value: "30", label: "+30 days" },
  { value: "90", label: "+90 days" },
  { value: "180", label: "+180 days" },
];

/** Mirrors the service: extends from the current expiry if still in the future, otherwise from today. */
function previewExpiry(expiresAt: string | undefined, days: number): Date {
  const now = new Date();
  const current = expiresAt ? new Date(expiresAt) : null;
  const base = current && current > now ? current : now;
  return addDays(base, days);
}

interface ExtendAccessModalProps {
  record: AccessRecord | null;
  onOpenChange: (open: boolean) => void;
}

export function ExtendAccessModal({ record, onOpenChange }: ExtendAccessModalProps) {
  const [days, setDays] = useState("30");
  const extend = useExtendAccess();

  const close = (open: boolean) => {
    if (extend.isPending) return;
    if (!open) setDays("30");
    onOpenChange(open);
  };

  const submit = () => {
    if (!record) return;
    extend.mutate(
      { id: record.id, days: Number(days) },
      {
        onSuccess: (updated) => {
          notify.success("Access extended", `${updated.studentName} now has access until ${formatDate(updated.expiresAt)}.`);
          setDays("30");
          onOpenChange(false);
        },
        onError: (err) => notify.error(err, "Couldn't extend access"),
      },
    );
  };

  const newExpiry = record ? previewExpiry(record.expiresAt, Number(days)) : null;

  return (
    <Modal
      open={record !== null}
      onOpenChange={close}
      title="Extend access"
      description={record ? `${record.studentName} · ${record.courseName}` : undefined}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={() => close(false)} disabled={extend.isPending}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={extend.isPending}>
            {extend.isPending && <Loader2 className="animate-spin" />}
            Extend access
          </Button>
        </>
      }
    >
      {record && (
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="extend-days">Extension</Label>
            <Select items={EXTENSION_OPTIONS} value={days} onValueChange={(v) => v && setDays(v)}>
              <SelectTrigger id="extend-days" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {EXTENSION_OPTIONS.map((o) => (
                  <SelectItem key={o.value} value={o.value}>
                    {o.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <dl className="grid grid-cols-2 gap-3 rounded-lg border bg-muted/40 p-3 text-sm">
            <div>
              <dt className="text-muted-foreground">Current expiry</dt>
              <dd className="font-medium tabular-nums">{record.expiresAt ? formatDate(record.expiresAt) : "None set"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">New expiry</dt>
              <dd className="font-medium text-primary tabular-nums" aria-live="polite">
                {formatDate(newExpiry)}
              </dd>
            </div>
          </dl>
        </div>
      )}
    </Modal>
  );
}
