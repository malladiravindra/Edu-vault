"use client";

import { useId, useRef, useState, type DragEvent } from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import { formatFileSize } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export const MAX_PDF_BYTES = 50 * 1024 * 1024;

/** Returns an error message, or null when the file is an acceptable PDF. */
export function validatePdf(file: File): string | null {
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) return `“${file.name}” isn't a PDF. Only PDF files can be uploaded.`;
  if (file.size === 0) return `“${file.name}” is empty.`;
  if (file.size > MAX_PDF_BYTES) {
    return `“${file.name}” is ${formatFileSize(file.size)}. The maximum file size is 50 MB.`;
  }
  return null;
}

export function fileBaseName(name: string) {
  return name.replace(/\.pdf$/i, "").replace(/[_-]+/g, " ").trim();
}

interface PdfDropzoneProps {
  file: File | null;
  onFileChange: (file: File | null) => void;
  disabled?: boolean;
  /** Accessible label for the dropzone group. */
  label?: string;
}

/** Single-PDF picker with drag & drop and a keyboard-accessible browse button. */
export function PdfDropzone({ file, onFileChange, disabled, label = "PDF file" }: PdfDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const errorId = useId();
  const hintId = useId();

  function accept(files: FileList | null) {
    if (!files || files.length === 0) return;
    if (files.length > 1) {
      setError("Drop one PDF at a time.");
      return;
    }
    const next = files[0];
    const message = validatePdf(next);
    setError(message);
    if (!message) onFileChange(next);
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragging(false);
    if (disabled) return;
    accept(e.dataTransfer.files);
  }

  if (file) {
    return (
      <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <FileText className="size-5" aria-hidden />
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium">{file.name}</p>
          <p className="text-xs text-muted-foreground tabular-nums">{formatFileSize(file.size)} · PDF</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={() => {
            onFileChange(null);
            setError(null);
          }}
          disabled={disabled}
          aria-label={`Remove ${file.name}`}
        >
          <X />
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      <div
        role="group"
        aria-label={label}
        aria-describedby={error ? errorId : hintId}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors",
          dragging ? "border-primary bg-primary/5" : "border-border hover:bg-muted/40",
          error && "border-destructive/60",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        <div className="flex size-11 items-center justify-center rounded-full bg-muted text-muted-foreground">
          <UploadCloud className="size-5" aria-hidden />
        </div>
        <div className="space-y-1">
          <p className="text-sm font-medium">
            Drag and drop a PDF here, or{" "}
            <Button
              type="button"
              variant="link"
              className="h-auto p-0 text-sm"
              onClick={(e) => {
                e.stopPropagation();
                inputRef.current?.click();
              }}
              disabled={disabled}
            >
              browse
            </Button>
          </p>
          <p id={hintId} className="text-xs text-muted-foreground">
            PDF only, up to 50 MB
          </p>
        </div>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => {
            accept(e.target.files);
            e.target.value = "";
          }}
        />
      </div>
      {error && (
        <p id={errorId} role="alert" className="text-xs font-medium text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
