"use client";

import { useState } from "react";
import type { Course, CourseStatus } from "@/types";
import { useSetCourseStatus } from "@/hooks/use-courses";
import { notify } from "@/lib/toast";
import { ConfirmationDialog } from "@/components/shared/confirmation-dialog";

export interface CourseStatusAction {
  target: CourseStatus;
  label: string;
}

/** Status transitions available from a course's current status. */
export function getCourseStatusActions(status: CourseStatus): CourseStatusAction[] {
  switch (status) {
    case "draft":
      return [
        { target: "published", label: "Publish" },
        { target: "archived", label: "Archive" },
      ];
    case "published":
      return [
        { target: "draft", label: "Unpublish" },
        { target: "archived", label: "Archive" },
      ];
    case "archived":
      return [
        { target: "published", label: "Publish" },
        { target: "draft", label: "Move to draft" },
      ];
  }
}

function copyFor(course: Course, target: CourseStatus) {
  switch (target) {
    case "published":
      return {
        title: `Publish “${course.name}”?`,
        description:
          "The course will appear in the student catalog and students can register based on its access model.",
        confirm: "Publish course",
        success: "Course published",
        destructive: false,
      };
    case "draft":
      return {
        title: course.status === "archived" ? `Move “${course.name}” to draft?` : `Unpublish “${course.name}”?`,
        description:
          "The course will be hidden from the student catalog and no new registrations will be accepted. Students who already have access keep it.",
        confirm: course.status === "archived" ? "Move to draft" : "Unpublish",
        success: course.status === "archived" ? "Course moved to draft" : "Course unpublished",
        destructive: false,
      };
    case "archived":
      return {
        title: `Archive “${course.name}”?`,
        description:
          "Archived courses are hidden from the catalog and can't receive new registrations. Existing students keep access to their resources until their access period ends.",
        confirm: "Archive course",
        success: "Course archived",
        destructive: true,
      };
  }
}

export interface CourseStatusRequest {
  course: Course;
  target: CourseStatus;
}

interface CourseStatusDialogProps {
  /** Last requested change. Stays set while closing so the dialog copy doesn't flash. */
  request: CourseStatusRequest | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/** Confirmation for publish / unpublish / archive. */
export function CourseStatusDialog({ request, open, onOpenChange }: CourseStatusDialogProps) {
  const setStatus = useSetCourseStatus();
  const copy = request ? copyFor(request.course, request.target) : null;

  return (
    <ConfirmationDialog
      open={open && Boolean(request)}
      onOpenChange={onOpenChange}
      title={copy?.title ?? ""}
      description={copy?.description ?? ""}
      confirmLabel={copy?.confirm}
      destructive={copy?.destructive}
      loading={setStatus.isPending}
      onConfirm={() => {
        if (!request || !copy) return;
        setStatus.mutate(
          { id: request.course.id, status: request.target },
          {
            onSuccess: () => {
              notify.success(copy.success, request.course.name);
              onOpenChange(false);
            },
            onError: (err) => notify.error(err, "Couldn't update course status"),
          },
        );
      }}
    />
  );
}

/** Local state helper for CourseStatusDialog. */
export function useCourseStatusDialog() {
  const [request, setRequest] = useState<CourseStatusRequest | null>(null);
  const [open, setOpen] = useState(false);
  return {
    request,
    open,
    onOpenChange: setOpen,
    ask: (course: Course, target: CourseStatus) => {
      setRequest({ course, target });
      setOpen(true);
    },
  };
}
