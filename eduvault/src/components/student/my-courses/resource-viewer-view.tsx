"use client";

import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";
import { PdfViewer } from "@/components/pdf-viewer";
import { useStudentCourse } from "@/hooks/use-courses";
import { usePublishedResources } from "@/hooks/use-resources";
import { useBreadcrumbLabel } from "@/components/layout/breadcrumbs";
import { Skeleton } from "@/components/ui/skeleton";

interface ResourceViewerViewProps {
  courseId: string;
  resourceId: string;
  initialPage: number;
}

export function ResourceViewerView({ courseId, resourceId, initialPage }: ResourceViewerViewProps) {
  const course = useStudentCourse(courseId);
  const resources = usePublishedResources(courseId);
  const resource = resources.data?.find((r) => r.id === resourceId);

  useBreadcrumbLabel(courseId, course.data?.name);
  useBreadcrumbLabel(resourceId, resource?.name);

  return (
    <div className="space-y-4">
      <div className="min-w-0 space-y-1">
        <Link
          href={`/student/my-courses/${courseId}`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground focus-visible:underline focus-visible:outline-none"
        >
          <ArrowLeft className="size-4" aria-hidden />
          {course.data?.name ?? "Back to course"}
        </Link>
        {resources.isLoading ? (
          <Skeleton className="h-7 w-64" />
        ) : (
          <h1 className="truncate text-xl font-semibold tracking-tight">{resource?.name ?? "Document"}</h1>
        )}
      </div>

      <PdfViewer resourceId={resourceId} mode="student" initialPage={initialPage} />

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <ShieldCheck className="mt-px size-3.5 shrink-0" aria-hidden />
        This document is protected. It&apos;s watermarked with your name and email and can&apos;t be downloaded.
      </p>
    </div>
  );
}
