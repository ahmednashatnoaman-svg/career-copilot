"use client";

import { useState } from "react";
import type { ApplicationPackage } from "@/lib/types";
import { Eye, X, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ApplicationRowProps {
  application: ApplicationPackage;
}

const statusBadgeConfig: Record<
  ApplicationPackage["status"],
  {
    label: string;
    bgColor: string;
    textColor: string;
  }
> = {
  APPROVED: {
    label: "Approved",
    bgColor: "bg-emerald-100 dark:bg-emerald-950",
    textColor: "text-emerald-800 dark:text-emerald-200",
  },
  DRAFT: {
    label: "Draft",
    bgColor: "bg-slate-100 dark:bg-slate-800",
    textColor: "text-slate-700 dark:text-slate-300",
  },
  SENT: {
    label: "Sent",
    bgColor: "bg-blue-100 dark:bg-blue-950",
    textColor: "text-blue-800 dark:text-blue-200",
  },
  REJECTED: {
    label: "Rejected",
    bgColor: "bg-red-100 dark:bg-red-950",
    textColor: "text-red-800 dark:text-red-200",
  },
  HUMAN_REQUIRED: {
    label: "Needs Review",
    bgColor: "bg-amber-100 dark:bg-amber-950",
    textColor: "text-amber-800 dark:text-amber-200",
  },
};

function StatusBadge({ status }: { status: ApplicationPackage["status"] }) {
  const config = statusBadgeConfig[status];
  return (
    <span
      className={cn(
        "inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium",
        config.bgColor,
        config.textColor
      )}
      aria-label={`Status: ${config.label}`}
    >
      {config.label}
    </span>
  );
}

export function ApplicationRow({ application }: ApplicationRowProps) {
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <div className="flex items-center justify-between gap-4 px-4 py-3 border-b border-border hover:bg-muted/30 transition-colors">
        {/* ── Company & Job Info ── */}
        <div className="flex-1 min-w-0">
          <p className="font-medium text-foreground truncate">
            {application.company}
          </p>
          <p className="text-sm text-muted-foreground truncate">
            {application.title}
          </p>
        </div>

        {/* ── Status Badge ── */}
        <div className="flex-shrink-0">
          <StatusBadge status={application.status} />
        </div>

        {/* ── View Action ── */}
        <div className="flex-shrink-0">
          {application.cover_letter && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowModal(true)}
              aria-label={`View cover letter for ${application.company}`}
              className="gap-2"
            >
              <Eye className="h-4 w-4" />
              <span className="hidden sm:inline">View</span>
            </Button>
          )}
        </div>
      </div>

      {/* ── Modal: View Cover Letter ── */}
      {showModal && application.cover_letter && (
        <div
          className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"
          onClick={() => setShowModal(false)}
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-title"
        >
          <div
            className="bg-background rounded-lg border border-border max-w-2xl w-full max-h-[80vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="sticky top-0 flex items-center justify-between gap-4 border-b border-border bg-background px-6 py-4">
              <div>
                <h2 id="modal-title" className="font-medium text-foreground">
                  {application.company} — {application.title}
                </h2>
                <p className="text-xs text-muted-foreground mt-1">
                  Generated on{" "}
                  {new Date(application.created_at).toLocaleDateString()}
                </p>
              </div>
              <button
                onClick={() => setShowModal(false)}
                aria-label="Close modal"
                className="flex-shrink-0 rounded-md p-1 hover:bg-muted transition-colors"
              >
                <X className="h-5 w-5 text-muted-foreground" />
              </button>
            </div>

            {/* Content */}
            <div className="px-6 py-6 prose prose-sm dark:prose-invert max-w-none">
              <div className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-foreground">
                {application.cover_letter}
              </div>
            </div>

            {/* Footer */}
            <div className="sticky bottom-0 flex items-center justify-end gap-3 border-t border-border bg-background px-6 py-4">
              <Button
                variant="outline"
                onClick={() => {
                  if (!application.cover_letter) return;
                  const blob = new Blob([application.cover_letter], { type: "text/plain" });
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `cover-letter-${application.company.toLowerCase().replace(/\s+/g, "-")}.txt`;
                  a.click();
                  URL.revokeObjectURL(url);
                }}
                className="gap-2"
                aria-label="Download application package"
              >
                <Download className="h-4 w-4" />
                Download
              </Button>
              <Button
                variant="outline"
                onClick={() => setShowModal(false)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
