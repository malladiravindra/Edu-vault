"use client";

import { useState, type ReactNode } from "react";
import type { Registration, RegistrationStatus } from "@/types";
import { formatPrice } from "@/lib/format";
import { notify } from "@/lib/toast";
import { useCourse } from "@/hooks/use-courses";
import { useUpdateRegistrationStatus } from "@/hooks/use-registrations";
import { ConfirmationDialog } from "@/components/shared/confirmation-dialog";
import { FormField } from "@/components/shared/form-field";
import { Textarea } from "@/components/ui/textarea";

export interface RegistrationDecision {
  registration: Registration;
  status: RegistrationStatus;
}

/** Menu / button labels for each admin decision. */
export const DECISION_LABEL: Record<RegistrationStatus, string> = {
  pending: "Keep Pending",
  immediate_access: "Grant Immediate Access",
  payment_required: "Require Payment",
};

export const DECISION_ORDER: RegistrationStatus[] = ["immediate_access", "payment_required", "pending"];

const SUCCESS_COPY: Record<RegistrationStatus, (r: Registration) => string> = {
  pending: (r) => `${r.studentName}'s registration is pending`,
  immediate_access: (r) => `Access granted to ${r.studentName}`,
  payment_required: (r) => `Payment requested from ${r.studentName}`,
};

interface RegistrationDecisionDialogProps {
  decision: RegistrationDecision | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDone?: (updated: Registration) => void;
}

export function RegistrationDecisionDialog({ decision, open, onOpenChange, onDone }: RegistrationDecisionDialogProps) {
  const [note, setNote] = useState("");
  const [noteFor, setNoteFor] = useState<RegistrationDecision | null>(decision);
  const mutation = useUpdateRegistrationStatus();
  const course = useCourse(decision?.status === "payment_required" ? decision.registration.courseId : undefined);

  // Reset the note whenever a new decision is opened (adjust state during render).
  if (decision !== noteFor) {
    setNoteFor(decision);
    setNote("");
  }

  if (!decision) return null;
  const { registration: reg, status } = decision;

  const priceText = course.data ? formatPrice(course.data.price, course.data.currency) : "the course fee";

  const copy: Record<RegistrationStatus, { title: string; description: ReactNode; confirm: string }> = {
    immediate_access: {
      title: "Grant immediate access?",
      description: (
        <>
          <span className="font-medium text-foreground">{reg.studentName}</span> will get access to{" "}
          <span className="font-medium text-foreground">{reg.courseName}</span> right away. They&apos;ll be notified by
          email.
        </>
      ),
      confirm: "Grant access",
    },
    payment_required: {
      title: "Require payment?",
      description: (
        <>
          <span className="font-medium text-foreground">{reg.studentName}</span> will be asked to pay{" "}
          <span className="font-medium text-foreground">{priceText}</span> before they can access{" "}
          <span className="font-medium text-foreground">{reg.courseName}</span>. Access unlocks automatically once the
          payment succeeds.
        </>
      ),
      confirm: "Require payment",
    },
    pending: {
      title: "Keep pending?",
      description: (
        <>
          The registration from <span className="font-medium text-foreground">{reg.studentName}</span> for{" "}
          <span className="font-medium text-foreground">{reg.courseName}</span>{" "}
          {reg.status === "pending" ? "will stay in" : "will move back to"} the review queue. The student won&apos;t
          have access until you make a decision.
        </>
      ),
      confirm: "Keep pending",
    },
  };
  const c = copy[status];

  const confirm = () => {
    mutation.mutate(
      { id: reg.id, status, note: note.trim() || undefined },
      {
        onSuccess: (updated) => {
          notify.success(SUCCESS_COPY[status](reg), reg.courseName);
          onOpenChange(false);
          onDone?.(updated);
        },
        onError: (err) => notify.error(err, "Couldn't update registration"),
      },
    );
  };

  return (
    <ConfirmationDialog
      open={open}
      onOpenChange={onOpenChange}
      title={c.title}
      description={c.description}
      confirmLabel={c.confirm}
      loading={mutation.isPending}
      onConfirm={confirm}
    >
      <FormField id="registration-note" label="Note (optional)" description="Saved with the decision for your team.">
        <Textarea
          id="registration-note"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Add context for this decision"
          rows={3}
          maxLength={500}
          disabled={mutation.isPending}
          aria-describedby="registration-note-description"
        />
      </FormField>
    </ConfirmationDialog>
  );
}
