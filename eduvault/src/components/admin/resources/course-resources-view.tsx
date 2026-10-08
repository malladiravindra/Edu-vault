"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowLeft, BookX, Eye, EyeOff, FileText, FileUp, MoreHorizontal, RefreshCw, Trash2, Upload } from "lucide-react";
import type { Resource } from "@/types";
import { formatDate, formatFileSize, formatNumber } from "@/lib/format";
import { notify } from "@/lib/toast";
import { useCourse } from "@/hooks/use-courses";
import { useCourseResources, useDeleteResource, useSetResourceStatus } from "@/hooks/use-resources";
import { useBreadcrumbLabel } from "@/components/layout/breadcrumbs";
import { PageHeader } from "@/components/shared/page-header";
import { DataTable, type DataTableColumn } from "@/components/shared/data-table";
import { ConfirmationDialog } from "@/components/shared/confirmation-dialog";
import { CourseStatusBadge, ResourceStatusBadge } from "@/components/shared/status-badge";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Modal } from "@/components/shared/modal";
import { DetailSkeleton } from "@/components/shared/loading-skeleton";
import { PdfViewer } from "@/components/pdf-viewer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { isNotFoundError } from "@/components/admin/courses/course-utils";
import { UploadResourceDialog } from "./upload-resource-dialog";
import { ReplaceResourceDialog } from "./replace-resource-dialog";

type DialogKind = "preview" | "replace" | "delete" | "status";

export function CourseResourcesView({ courseId }: { courseId: string }) {
  const courseQuery = useCourse(courseId);
  const course = courseQuery.data;
  useBreadcrumbLabel(courseId, course?.name);

  const resourcesQuery = useCourseResources(courseId);
  const setStatus = useSetResourceStatus();
  const remove = useDeleteResource();

  const [uploadOpen, setUploadOpen] = useState(false);
  const [dialog, setDialog] = useState<DialogKind | null>(null);
  const [selected, setSelected] = useState<Resource | null>(null);

  const openDialog = (kind: DialogKind, resource: Resource) => {
    setSelected(resource);
    setDialog(kind);
  };
  const closeDialog = () => setDialog(null);

  if (courseQuery.isLoading) return <DetailSkeleton />;
  if (courseQuery.error || !course) {
    if (isNotFoundError(courseQuery.error)) {
      return (
        <EmptyState
          icon={BookX}
          title="Course not found"
          description="This course may have been removed, or the link is incorrect."
          action={
            <Button variant="outline" nativeButton={false} render={<Link href="/admin/resources" />}>
              <ArrowLeft />
              Back to resources
            </Button>
          }
        />
      );
    }
    return (
      <ErrorState error={courseQuery.error} onRetry={() => courseQuery.refetch()} retrying={courseQuery.isFetching} />
    );
  }

  const columns: DataTableColumn<Resource>[] = [
    {
      id: "name",
      header: "Resource",
      className: "min-w-60 max-w-96 whitespace-normal",
      cell: (r) => (
        <div className="flex items-start gap-3">
          <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
            <FileText className="size-4" aria-hidden />
          </div>
          <div className="min-w-0">
            <p className="font-medium">{r.name}</p>
            {r.description && <p className="line-clamp-1 text-xs text-muted-foreground">{r.description}</p>}
          </div>
        </div>
      ),
    },
    {
      id: "type",
      header: "Type",
      hideBelow: "md",
      cell: (r) => (
        <Badge variant="outline" className="uppercase">
          {r.type}
        </Badge>
      ),
    },
    {
      id: "pages",
      header: "Pages",
      align: "right",
      hideBelow: "sm",
      cell: (r) => <span className="tabular-nums">{r.status === "processing" ? "—" : formatNumber(r.pageCount)}</span>,
    },
    {
      id: "size",
      header: "Size",
      align: "right",
      hideBelow: "lg",
      cell: (r) => <span className="text-muted-foreground tabular-nums">{formatFileSize(r.fileSizeBytes)}</span>,
    },
    { id: "status", header: "Status", cell: (r) => <ResourceStatusBadge status={r.status} /> },
    {
      id: "created",
      header: "Created",
      hideBelow: "lg",
      cell: (r) => <span className="text-muted-foreground tabular-nums">{formatDate(r.createdAt)}</span>,
    },
    {
      id: "actions",
      header: <span className="sr-only">Actions</span>,
      align: "right",
      cell: (r) => {
        const processing = r.status === "processing";
        return (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon-sm" aria-label={`Actions for ${r.name}`} />}
            >
              <MoreHorizontal />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuItem disabled={processing} onClick={() => openDialog("preview", r)}>
                <Eye />
                Preview
              </DropdownMenuItem>
              <DropdownMenuItem disabled={processing} onClick={() => openDialog("status", r)}>
                {r.status === "published" ? <EyeOff /> : <Upload />}
                {r.status === "published" ? "Unpublish" : "Publish"}
              </DropdownMenuItem>
              <DropdownMenuItem disabled={processing} onClick={() => openDialog("replace", r)}>
                <RefreshCw />
                Replace file
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={() => openDialog("delete", r)}>
                <Trash2 />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        );
      },
    },
  ];

  const willPublish = selected?.status !== "published";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={
          <Link
            href={`/admin/courses/${course.id}`}
            className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            {course.name}
          </Link>
        }
        title={`${course.name} — Resources`}
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            Protected PDFs available to students enrolled in this course.
            <CourseStatusBadge status={course.status} />
          </span>
        }
        actions={
          <Button onClick={() => setUploadOpen(true)}>
            <FileUp />
            Upload PDF
          </Button>
        }
      />

      <DataTable
        columns={columns}
        data={resourcesQuery.data}
        getRowId={(r) => r.id}
        isLoading={resourcesQuery.isLoading}
        isFetching={resourcesQuery.isFetching}
        error={resourcesQuery.error}
        onRetry={() => resourcesQuery.refetch()}
        emptyIcon={FileText}
        emptyTitle="No resources yet"
        emptyDescription="Upload a PDF to make it available to enrolled students in the secure viewer."
        emptyAction={
          <Button onClick={() => setUploadOpen(true)}>
            <FileUp />
            Upload PDF
          </Button>
        }
        caption={`Resources for ${course.name}`}
      />

      <UploadResourceDialog courseId={course.id} open={uploadOpen} onOpenChange={setUploadOpen} />

      <ReplaceResourceDialog
        resource={selected}
        open={dialog === "replace"}
        onOpenChange={(open) => !open && closeDialog()}
      />

      <Modal
        open={dialog === "preview" && Boolean(selected)}
        onOpenChange={(open) => !open && closeDialog()}
        size="xl"
        title={selected ? `Preview: ${selected.name}` : "Preview"}
        description="Admin preview. Students see the same server-rendered pages with their personal watermark."
      >
        {dialog === "preview" && selected && (
          <PdfViewer resourceId={selected.id} mode="admin-preview" className="h-[70dvh]" />
        )}
      </Modal>

      <ConfirmationDialog
        open={dialog === "status" && Boolean(selected)}
        onOpenChange={(open) => !open && closeDialog()}
        title={selected ? `${willPublish ? "Publish" : "Unpublish"} “${selected.name}”?` : ""}
        description={
          willPublish
            ? "Enrolled students with active access will be able to open this resource in the secure viewer."
            : "Students will no longer see this resource. You can publish it again at any time."
        }
        confirmLabel={willPublish ? "Publish" : "Unpublish"}
        loading={setStatus.isPending}
        onConfirm={() => {
          if (!selected) return;
          setStatus.mutate(
            { id: selected.id, status: willPublish ? "published" : "draft" },
            {
              onSuccess: () => {
                notify.success(willPublish ? "Resource published" : "Resource unpublished", selected.name);
                closeDialog();
              },
              onError: (err) => notify.error(err, "Couldn't update resource"),
            },
          );
        }}
      />

      <ConfirmationDialog
        open={dialog === "delete" && Boolean(selected)}
        onOpenChange={(open) => !open && closeDialog()}
        destructive
        title={selected ? `Delete “${selected.name}”?` : ""}
        description={
          <>
            This permanently removes <span className="font-medium text-foreground">{selected?.name}</span> from{" "}
            {course.name}. Students lose access to it immediately and their reading progress for it is discarded. This
            can&apos;t be undone.
          </>
        }
        confirmLabel="Delete resource"
        loading={remove.isPending}
        onConfirm={() => {
          if (!selected) return;
          remove.mutate(selected.id, {
            onSuccess: () => {
              notify.success("Resource deleted", selected.name);
              closeDialog();
            },
            onError: (err) => notify.error(err, "Couldn't delete resource"),
          });
        }}
      />
    </div>
  );
}
