"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, FileText, CheckCircle2, AlertCircle, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { uploadDocument } from "@/lib/api";

interface UploadedFile {
  name: string;
  status: "uploading" | "done" | "error";
  chunks?: number;
  error?: string;
}

interface UploadDropzoneProps {
  userId: string;
  className?: string;
}

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/msword",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
];

const ACCEPTED_EXTENSIONS = ".pdf,.doc,.docx,.txt";

export function UploadDropzone({ userId, className }: UploadDropzoneProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const processFiles = useCallback(
    async (incoming: FileList | File[]) => {
      const list = Array.from(incoming);
      if (list.length === 0) return;

      // Add all as "uploading"
      setFiles((prev) => [
        ...prev,
        ...list.map((f) => ({ name: f.name, status: "uploading" as const })),
      ]);

      await Promise.all(
        list.map(async (file) => {
          try {
            const res = await uploadDocument(userId, file);
            setFiles((prev) =>
              prev.map((f) =>
                f.name === file.name && f.status === "uploading"
                  ? { ...f, status: "done", chunks: res.chunks }
                  : f
              )
            );
          } catch (err) {
            const msg = err instanceof Error ? err.message : "Upload failed";
            setFiles((prev) =>
              prev.map((f) =>
                f.name === file.name && f.status === "uploading"
                  ? { ...f, status: "error", error: msg }
                  : f
              )
            );
          }
        })
      );
    },
    [userId]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragging(false);
      processFiles(e.dataTransfer.files);
    },
    [processFiles]
  );

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => setIsDragging(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      processFiles(e.target.files);
      // Reset so same file can be re-uploaded
      e.target.value = "";
    }
  };

  const removeFile = (name: string) => {
    setFiles((prev) => prev.filter((f) => f.name !== name));
  };

  return (
    <div className={cn("space-y-4", className)}>
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload documents — drag and drop or click to browse"
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={cn(
          "relative flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-8 py-14 text-center transition-colors cursor-pointer",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-border bg-muted/40 hover:border-primary/50 hover:bg-muted/70"
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS}
          className="sr-only"
          onChange={handleChange}
          aria-hidden="true"
        />

        <div
          className={cn(
            "flex h-12 w-12 items-center justify-center rounded-full border transition-colors",
            isDragging
              ? "border-primary bg-primary/10 text-primary"
              : "border-border bg-background text-muted-foreground"
          )}
        >
          <Upload className="h-5 w-5" />
        </div>

        <div>
          <p className="text-sm font-medium text-foreground">
            Drop files here, or{" "}
            <span className="text-primary underline underline-offset-2">
              browse
            </span>
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            PDF, DOCX, DOC or TXT — resume, certificates, portfolio
          </p>
        </div>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <ul className="space-y-2" aria-label="Uploaded files">
          {files.map((f, i) => (
            <li
              key={`${f.name}-${i}`}
              className="card-warm flex items-center gap-3 px-4 py-3"
            >
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />

              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {f.name}
                </p>
                {f.status === "uploading" && (
                  <p className="text-xs text-muted-foreground animate-pulse">
                    Uploading…
                  </p>
                )}
                {f.status === "done" && f.chunks !== undefined && (
                  <p className="text-xs text-primary">
                    Ingested — {f.chunks} chunk{f.chunks !== 1 ? "s" : ""}
                  </p>
                )}
                {f.status === "error" && (
                  <p className="text-xs text-destructive">{f.error}</p>
                )}
              </div>

              <div className="shrink-0" aria-hidden="true">
                {f.status === "uploading" && (
                  <div className="h-4 w-4 rounded-full border-2 border-primary border-t-transparent animate-spin" />
                )}
                {f.status === "done" && (
                  <CheckCircle2 className="h-4 w-4 text-primary" />
                )}
                {f.status === "error" && (
                  <AlertCircle className="h-4 w-4 text-destructive" />
                )}
              </div>

              <button
                onClick={() => removeFile(f.name)}
                aria-label={`Remove ${f.name}`}
                className="shrink-0 rounded p-1 text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
