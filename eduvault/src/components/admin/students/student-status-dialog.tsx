"use client";

import { useState } from "react";
import type { Student } from "@/types";
import { notify } from "@/lib/toast";
import { useReinstateStudent, useSuspendStudent } from "@/hooks/use-students";
import { ConfirmationDialog } from "@/components/shared/confirmation-dialog";
import { FormField } from "@/components/shared/form-field";
import { Textarea } from "@/components/ui/textarea";

interface StudentStatusDialogProps {
  /** Student being suspended (if active/pending) or reinstated (if suspended). */
  student: Student | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Confirms suspending or reinstating a student account. */
export function StudentStatusDialog({ student, open, onOpenChange }: StudentStatusDialogProps) {
  const [reason, setReason] = useState("");
  const [reasonFor, setReasonFor] = useState<Student | null>(student);
  const suspend = useSuspendStudent();
  const reinstate = useReinstateStudent();

  // Reset the reason when the dialog targets a different student.
  if (student !== reasonFor) {
    setReasonFor(student);
    setReason("");
  }

  if (!student) return null;
  const isSuspended = student.status === "suspended";
  const pending = suspend.isPending || reinstate.isPending;

  const confirm = () => {
    if (isSuspended) {
      reinstate.mutate(student.id, {
        onSuccess: () => {
          notify.success(`${student.name} reinstated`, "Their account and course access have been restored.");
          onOpenChange(false);
        },
        onError: (err) => notify.error(err, "Couldn't reinstate student"),
      });
    } else {
      suspend.mutate(
        { id: student.id, reason: reason.trim() || undefined },
        {
          onSuccess: () => {
            notify.success(`${student.name} suspended`, "Their active course access has been suspended.");
            onOpenChange(false);
          },
          onError: (err) => notify.error(err, "Couldn't suspend student"),
        },
      );
    }
  };

  if (isSuspended) {
    return (
      <ConfirmationDialog
        open={open}
        onOpenChange={onOpenChange}
        title={`Reinstate ${student.name}?`}
        description="They'll be able to sign in again and their suspended course access will be restored."
        confirmLabel="Reinstate student"
        loading={pending}
        onConfirm={confirm}
      />
    );
  }

  return (
    <ConfirmationDialog
      open={open}
      onOpenChange={onOpenChange}
      destructive
      title={`Suspend ${student.name}?`}
      description="They'll be signed out and won't be able to sign in. All of their active course access will be suspended too until you reinstate them."
      confirmLabel="Suspend student"
      loading={pending}
      onConfirm={confirm}
    >
      <FormField id="suspend-reason" label="Reason (optional)" description="Recorded in the audit log.">
        <Textarea
          id="suspend-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="e.g. Account sharing detected"
          rows={3}
          maxLength={500}
          disabled={pending}
          aria-describedby="suspend-reason-description"
        />
      </FormField>
    </ConfirmationDialog>
  );
}
