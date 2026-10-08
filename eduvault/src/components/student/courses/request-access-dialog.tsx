"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Clock, Info, Loader2 } from "lucide-react";
import type { StudentCourse } from "@/types";
import { formatAccessDuration, formatPrice } from "@/lib/format";
import { notify } from "@/lib/toast";
import { useRequestAccess } from "@/hooks/use-registrations";
import { Modal } from "@/components/shared/modal";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { requestAccessSchema, type RequestAccessValues } from "./request-access-schema";

const FORM_ID = "request-access-form";

/** Plain-language explanation of what happens after the request is submitted. */
export function accessModelExplanation(course: Pick<StudentCourse, "accessModel" | "price">): string {
  if (course.accessModel === "free") {
    return "This course is free. Access is granted instantly once your request is confirmed.";
  }
  if (course.accessModel === "paid" || course.price > 0) {
    return "Your request will be reviewed by our team. Once approved, you'll be asked to pay to unlock the course.";
  }
  return "This course is free, but access requires approval. We'll notify you as soon as your request is reviewed.";
}

interface RequestAccessDialogProps {
  course: StudentCourse | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RequestAccessDialog({ course, open, onOpenChange }: RequestAccessDialogProps) {
  const requestAccess = useRequestAccess();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<RequestAccessValues>({ resolver: zodResolver(requestAccessSchema), defaultValues: { message: "" } });

  const handleOpenChange = (next: boolean) => {
    if (requestAccess.isPending) return;
    if (!next) reset();
    onOpenChange(next);
  };

  const onSubmit = (values: RequestAccessValues) => {
    if (!course) return;
    requestAccess.mutate(
      { courseId: course.id, message: values.message || undefined },
      {
        onSuccess: () => {
          notify.success("Request submitted — we'll notify you when it's reviewed.");
          reset();
          onOpenChange(false);
        },
        onError: (err) => notify.error(err, "Couldn't submit your request"),
      },
    );
  };

  return (
    <Modal
      open={open}
      onOpenChange={handleOpenChange}
      title={course ? `Request access to ${course.name}` : "Request access"}
      description="Tell us a little about why you'd like to join. This is optional."
      footer={
        <>
          <Button variant="outline" onClick={() => handleOpenChange(false)} disabled={requestAccess.isPending}>
            Cancel
          </Button>
          <Button type="submit" form={FORM_ID} disabled={requestAccess.isPending || !course}>
            {requestAccess.isPending && <Loader2 className="animate-spin" aria-hidden />}
            {requestAccess.isPending ? "Submitting…" : "Submit request"}
          </Button>
        </>
      }
    >
      {course && (
        <form id={FORM_ID} onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div className="rounded-lg border bg-muted/30 p-4">
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm text-muted-foreground">Price</span>
              <span className="text-lg font-semibold tabular-nums">{formatPrice(course.price, course.currency)}</span>
            </div>
            <div className="mt-1 flex items-center justify-between gap-3 text-sm">
              <span className="text-muted-foreground">Access</span>
              <span className="inline-flex items-center gap-1.5">
                <Clock className="size-3.5 text-muted-foreground" aria-hidden />
                {formatAccessDuration(course.accessDurationDays)}
              </span>
            </div>
            <p className="mt-3 flex gap-2 border-t pt-3 text-sm text-muted-foreground">
              <Info className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              {accessModelExplanation(course)}
            </p>
          </div>

          <FormField
            id="request-message"
            label="Message (optional)"
            error={errors.message?.message}
            description="Up to 500 characters."
          >
            <Textarea
              id="request-message"
              rows={4}
              placeholder="e.g. I'm preparing for a certification and this course covers the core topics."
              aria-invalid={!!errors.message}
              aria-describedby={fieldDescribedBy("request-message", errors.message, true)}
              {...register("message")}
            />
          </FormField>
        </form>
      )}
    </Modal>
  );
}
