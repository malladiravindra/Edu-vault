"use client";

import { useState } from "react";
import { Info, Loader2 } from "lucide-react";
import type { Resource } from "@/types";
import { formatFileSize } from "@/lib/format";
import { useReplaceResource } from "@/hooks/use-resources";
import { notify } from "@/lib/toast";
import { Modal } from "@/components/shared/modal";
import { ProgressBar } from "@/components/shared/progress-bar";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { PdfDropzone } from "./pdf-dropzone";

interface ReplaceResourceDialogProps {
  /** Last selected resource; kept set while closing so the copy doesn't flash. */
  resource: Resource | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function ReplaceResourceDialog({ resource, open, onOpenChange }: ReplaceResourceDialogProps) {
  const replace = useReplaceResource();

  return (
    <Modal
      open={open && Boolean(resource)}
      onOpenChange={(next) => !replace.isPending && onOpenChange(next)}
      title="Replace file"
      description={resource ? `Upload a new PDF for “${resource.name}”.` : undefined}
    >
      {open && resource && (
        <ReplaceForm
          key={resource.id}
          resource={resource}
          replace={replace}
          onDone={() => onOpenChange(false)}
          onCancel={() => onOpenChange(false)}
        />
      )}
    </Modal>
  );
}

interface ReplaceFormProps {
  resource: Resource;
  replace: ReturnType<typeof useReplaceResource>;
  onDone: () => void;
  onCancel: () => void;
}

function ReplaceForm({ resource, replace, onDone, onCancel }: ReplaceFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const uploading = replace.isPending;

  function submit() {
    if (!file) return;
    setProgress(0);
    replace.mutate(
      { id: resource.id, file, onProgress: setProgress },
      {
        onSuccess: () => {
          notify.success("File replaced", `Students will now see the new version of ${resource.name}.`);
          onDone();
        },
        onError: (err) => notify.error(err, "Couldn't replace file"),
      },
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-start gap-2 rounded-lg border bg-muted/30 p-3 text-sm">
        <Info className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
        <p className="text-muted-foreground">
          The current file ({resource.pageCount} pages, {formatFileSize(resource.fileSizeBytes)}) will be replaced.
          Students with access will see the new version the next time they open it. Reading progress may reset if
          the page count changes.
        </p>
      </div>

      <PdfDropzone file={file} onFileChange={setFile} disabled={uploading} label="Replacement PDF" />

      {uploading && (
        <div className="space-y-1.5" aria-live="polite">
          <p className="text-sm font-medium">Uploading…</p>
          <ProgressBar value={progress} size="md" label="Upload progress" />
        </div>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel} disabled={uploading}>
          Cancel
        </Button>
        <Button type="button" onClick={submit} disabled={!file || uploading}>
          {uploading && <Loader2 className="animate-spin" />}
          {uploading ? "Uploading…" : "Replace file"}
        </Button>
      </DialogFooter>
    </div>
  );
}
