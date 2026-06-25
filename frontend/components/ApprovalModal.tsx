"use client";

/**
 * ApprovalModal — HITL gate component.
 *
 * Renders a blocking modal when an `interrupt` event arrives.
 * Nothing is sent/approved without an explicit user click.
 *
 * Accessibility:
 * - Focus is trapped inside while open (managed via useEffect + tabbable refs)
 * - Esc key dismisses (triggers reject path) unless a submit is in-flight
 * - aria-modal, aria-labelledby, aria-describedby wired up
 * - Role="dialog" on the panel
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { X, CheckCircle2, XCircle, Edit3 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { HitlRequest, ApplicationPackage } from "@/lib/types";

export type ApprovalDecision =
  | { approved: true; editedPackage?: Partial<ApplicationPackage> }
  | { approved: false };

interface ApprovalModalProps {
  open: boolean;
  hitlRequest: HitlRequest;
  applicationPackage?: ApplicationPackage | null;
  isSubmitting: boolean;
  onDecide: (decision: ApprovalDecision) => void;
  onClose: () => void;
}

export function ApprovalModal({
  open,
  hitlRequest,
  applicationPackage,
  isSubmitting,
  onDecide,
  onClose,
}: ApprovalModalProps) {
  const [mode, setMode] = useState<"review" | "edit">("review");
  const [editedCoverLetter, setEditedCoverLetter] = useState(
    applicationPackage?.cover_letter ?? ""
  );
  const [editedResumeSummary, setEditedResumeSummary] = useState(
    applicationPackage?.resume_snapshot ?? ""
  );

  const dialogRef = useRef<HTMLDivElement>(null);
  const firstFocusRef = useRef<HTMLButtonElement>(null);
  const titleId = "approval-modal-title";
  const descId = "approval-modal-desc";

  // Sync edited state when package changes
  useEffect(() => {
    setEditedCoverLetter(applicationPackage?.cover_letter ?? "");
    setEditedResumeSummary(applicationPackage?.resume_snapshot ?? "");
    setMode("review");
  }, [applicationPackage]);

  // Focus trap: on open, move focus to first focusable element
  useEffect(() => {
    if (open) {
      setTimeout(() => firstFocusRef.current?.focus(), 50);
    }
  }, [open]);

  // Keyboard handler: Esc to close
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape" && !isSubmitting) {
        onClose();
      }

      // Tab trap: keep focus inside dialog
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }
    },
    [isSubmitting, onClose]
  );

  const handleApprove = () => {
    if (mode === "edit") {
      onDecide({
        approved: true,
        editedPackage: {
          cover_letter: editedCoverLetter,
          resume_snapshot: editedResumeSummary,
        },
      });
    } else {
      onDecide({ approved: true });
    }
  };

  const handleReject = () => {
    onDecide({ approved: false });
  };

  if (!open) return null;

  return (
    /* Backdrop */
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      aria-hidden="false"
    >
      {/* Dimmed overlay */}
      <div
        className="absolute inset-0 bg-foreground/40 backdrop-blur-sm"
        aria-hidden="true"
        onClick={!isSubmitting ? onClose : undefined}
      />

      {/* Modal panel */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={descId}
        onKeyDown={handleKeyDown}
        className={cn(
          "relative z-10 w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto",
          "bg-card border border-border rounded-lg",
          "shadow-[0_8px_32px_hsl(30_20%_40%/0.18),0_2px_8px_hsl(30_20%_40%/0.12)]"
        )}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-6 pt-6 pb-4 border-b border-border">
          <div>
            {/* Editorial accent rule */}
            <span className="block h-px w-8 bg-primary mb-3" aria-hidden="true" />
            <h2
              id={titleId}
              className="font-display text-xl font-semibold text-foreground leading-tight"
            >
              Review Application
            </h2>
            <p id={descId} className="mt-1 text-sm text-muted-foreground">
              {hitlRequest.question}
            </p>
          </div>
          <button
            type="button"
            onClick={!isSubmitting ? onClose : undefined}
            disabled={isSubmitting}
            className="ml-4 mt-0.5 rounded-md p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5 space-y-5">
          {applicationPackage ? (
            <>
              {/* Job context */}
              <div className="rounded-md bg-muted/50 border border-border px-4 py-3">
                <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-1">
                  Position
                </p>
                <p className="text-sm font-semibold text-foreground">
                  {applicationPackage.title}
                  {applicationPackage.company && (
                    <span className="font-normal text-muted-foreground">
                      {" "}
                      at {applicationPackage.company}
                    </span>
                  )}
                </p>
              </div>

              {/* Cover letter */}
              {(applicationPackage.cover_letter || mode === "edit") && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Cover Letter
                    </p>
                    {mode === "review" && (
                      <button
                        type="button"
                        onClick={() => setMode("edit")}
                        className="flex items-center gap-1 text-xs text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
                      >
                        <Edit3 className="h-3 w-3" />
                        Edit
                      </button>
                    )}
                  </div>
                  {mode === "edit" ? (
                    <textarea
                      value={editedCoverLetter}
                      onChange={(e) => setEditedCoverLetter(e.target.value)}
                      rows={8}
                      className={cn(
                        "w-full text-sm text-foreground bg-background border border-input rounded-md px-3 py-2",
                        "focus:outline-none focus:ring-2 focus:ring-ring resize-y",
                        "placeholder:text-muted-foreground"
                      )}
                      aria-label="Edit cover letter"
                    />
                  ) : (
                    <div className="text-sm text-foreground whitespace-pre-wrap bg-muted/30 border border-border rounded-md px-4 py-3 max-h-48 overflow-y-auto leading-relaxed">
                      {applicationPackage.cover_letter}
                    </div>
                  )}
                </div>
              )}

              {/* Resume snapshot */}
              {(applicationPackage.resume_snapshot || mode === "edit") && (
                <div>
                  <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">
                    Tailored CV Summary
                  </p>
                  {mode === "edit" ? (
                    <textarea
                      value={editedResumeSummary}
                      onChange={(e) => setEditedResumeSummary(e.target.value)}
                      rows={5}
                      className={cn(
                        "w-full text-sm text-foreground bg-background border border-input rounded-md px-3 py-2",
                        "focus:outline-none focus:ring-2 focus:ring-ring resize-y",
                        "placeholder:text-muted-foreground"
                      )}
                      aria-label="Edit CV summary"
                    />
                  ) : (
                    <div className="text-sm text-foreground whitespace-pre-wrap bg-muted/30 border border-border rounded-md px-4 py-3 max-h-32 overflow-y-auto leading-relaxed">
                      {applicationPackage.resume_snapshot}
                    </div>
                  )}
                </div>
              )}

              {mode === "edit" && (
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => setMode("review")}
                    disabled={isSubmitting}
                  >
                    Preview
                  </Button>
                </div>
              )}
            </>
          ) : (
            /* No package — show raw HITL context */
            <div className="rounded-md bg-muted/50 border border-border px-4 py-3">
              <p className="text-sm text-muted-foreground italic">
                No application package details available.
              </p>
              {hitlRequest.context && (
                <pre className="mt-2 text-xs text-foreground/70 whitespace-pre-wrap overflow-auto max-h-40">
                  {JSON.stringify(hitlRequest.context, null, 2)}
                </pre>
              )}
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="flex flex-col-reverse sm:flex-row items-center justify-end gap-3 px-6 pb-6 pt-4 border-t border-border">
          <Button
            ref={firstFocusRef}
            variant="outline"
            onClick={handleReject}
            disabled={isSubmitting}
            className="w-full sm:w-auto gap-2 text-destructive border-destructive/30 hover:bg-destructive/5 hover:text-destructive"
            aria-label="Reject application — nothing will be sent"
          >
            <XCircle className="h-4 w-4" />
            Reject
          </Button>

          {mode === "review" && (
            <Button
              variant="outline"
              onClick={() => setMode("edit")}
              disabled={isSubmitting}
              className="w-full sm:w-auto gap-2"
              aria-label="Edit application before approving"
            >
              <Edit3 className="h-4 w-4" />
              Edit
            </Button>
          )}

          <Button
            onClick={handleApprove}
            disabled={isSubmitting}
            className="w-full sm:w-auto gap-2"
            aria-label="Approve and send application"
          >
            {isSubmitting ? (
              <>
                <span
                  className="h-4 w-4 rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground animate-spin"
                  aria-hidden="true"
                />
                Sending…
              </>
            ) : (
              <>
                <CheckCircle2 className="h-4 w-4" />
                {mode === "edit" ? "Save & Approve" : "Approve"}
              </>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
