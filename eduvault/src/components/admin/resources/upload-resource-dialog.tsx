"use client";

import { useState, type FormEvent } from "react";
import { Loader2, ShieldCheck } from "lucide-react";
import { useUploadResource } from "@/hooks/use-resources";
import { notify } from "@/lib/toast";
import { Modal } from "@/components/shared/modal";
import { FormField, fieldDescribedBy } from "@/components/shared/form-field";
import { ProgressBar } from "@/components/shared/progress-bar";
import { Button } from "@/components/ui/button";
import { DialogFooter } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { PdfDropzone, fileBaseName } from "./pdf-dropzone";

interface UploadResourceDialogProps {
  courseId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function UploadResourceDialog({ courseId, open, onOpenChange }: UploadResourceDialogProps) {
  const upload = useUploadResource(courseId);

  return (
    <Modal
      open={open}
      onOpenChange={(next) => !upload.isPending && onOpenChange(next)}
      title="Upload PDF"
      description="Add a protected PDF resource to this course."
    >
      {/* Mounted only while open, so the form resets each time the dialog opens. */}
      {open && <UploadForm upload={upload} onDone={() => onOpenChange(false)} onCancel={() => onOpenChange(false)} />}
    </Modal>
  );
}

interface UploadFormProps {
  upload: ReturnType<typeof useUploadResource>;
  onDone: () => void;
  onCancel: () => void;
}

function UploadForm({ upload, onDone, onCancel }: UploadFormProps) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [nameEdited, setNameEdited] = useState(false);
  const [description, setDescription] = useState("");
  const [publish, setPublish] = useState(true);
  const [progress, setProgress] = useState(0);
  const [submitted, setSubmitted] = useState(false);

  const uploading = upload.isPending;
  const fileError = submitted && !file ? "Choose a PDF to upload" : undefined;
  const trimmedName = name.trim();
  const nameError =
    submitted && trimmedName.length < 2
      ? "Enter a resource name"
      : trimmedName.length > 120
        ? "Keep the name under 120 characters"
        : undefined;

  function handleFile(next: File | null) {
    setFile(next);
    if (next && (!nameEdited || name.trim() === "")) {
      setName(fileBaseName(next.name));
      setNameEdited(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    if (!file || trimmedName.length < 2 || trimmedName.length > 120) return;
    setProgress(0);
    upload.mutate(
      {
        input: { file, name: trimmedName, description: description.trim() || undefined, publish },
        onProgress: setProgress,
      },
      {
        onSuccess: (resource) => {
          notify.success("Resource uploaded", `${resource.name} is ${publish ? "published" : "saved as unpublished"}.`);
          onDone();
        },
        onError: (err) => notify.error(err, "Upload failed"),
      },
    );
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div className="space-y-1.5">
        <PdfDropzone file={file} onFileChange={handleFile} disabled={uploading} />
        {fileError && (
          <p role="alert" className="text-xs font-medium text-destructive">
            {fileError}
          </p>
        )}
      </div>

      <FormField id="resource-name" label="Resource name" error={nameError} required>
        <Input
          id="resource-name"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setNameEdited(true);
          }}
          disabled={uploading}
          placeholder="e.g. Module 1 — Foundations"
          aria-invalid={!!nameError}
          aria-describedby={fieldDescribedBy("resource-name", nameError)}
        />
      </FormField>

      <FormField id="resource-description" label="Description" description="Optional. Shown to students in the course.">
        <Textarea
          id="resource-description"
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          disabled={uploading}
          aria-describedby="resource-description-description"
        />
      </FormField>

      <div className="flex items-start justify-between gap-4 rounded-lg border p-3">
        <div className="space-y-0.5">
          <Label htmlFor="resource-publish">Publish immediately</Label>
          <p className="text-xs text-muted-foreground">Enrolled students can open it as soon as processing finishes.</p>
        </div>
        <Switch id="resource-publish" checked={publish} onCheckedChange={setPublish} disabled={uploading} />
      </div>

      {uploading && (
        <div className="space-y-1.5" aria-live="polite">
          <p className="text-sm font-medium">Uploading…</p>
          <ProgressBar value={progress} size="md" label="Upload progress" />
        </div>
      )}

      <p className="flex items-start gap-2 text-xs text-muted-foreground">
        <ShieldCheck className="mt-px size-3.5 shrink-0" aria-hidden />
        Files are uploaded to secure storage and rendered server-side. Students never receive the original PDF.
      </p>

      <DialogFooter>
        <Button type="button" variant="outline" onClick={onCancel} disabled={uploading}>
          Cancel
        </Button>
        <Button type="submit" disabled={uploading}>
          {uploading && <Loader2 className="animate-spin" />}
          {uploading ? "Uploading…" : "Upload PDF"}
        </Button>
      </DialogFooter>
    </form>
  );
}
