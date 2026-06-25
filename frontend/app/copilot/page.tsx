"use client";

/**
 * Copilot page — streaming chat with HITL approval gate.
 *
 * State machine:
 *   idle → (user submits) → streaming → (interrupt event) → awaiting-approval
 *       → (approve/reject) → streaming (resumed) → done
 *                         or → done (rejected)
 *   streaming → done  (no interrupt path)
 *   any → error
 *
 * HITL blocking: when `interrupt` arrives from useSSE, status is set to
 * "awaiting-approval" AND `approvalOpen` is set to true. The ApprovalModal
 * renders as a blocking overlay; NO resume call is made until the user
 * explicitly clicks Approve or Reject. The run remains paused server-side
 * until api.resumeRun is called.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { SendHorizonal, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Header } from "@/components/header";
import { ChatStream, type CopilotStatus } from "@/components/ChatStream";
import { ApprovalModal, type ApprovalDecision } from "@/components/ApprovalModal";
import { useSSE } from "@/lib/useSSE";
import { startRun, resumeRun } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { ApplicationPackage } from "@/lib/types";

// ── Demo user (auth deferred) ────────────────────────────────

function getDemoUserId(): string {
  if (typeof window === "undefined") return "demo-user";
  const stored = localStorage.getItem("copilot_user_id");
  if (stored) return stored;
  const id = `demo-${Math.random().toString(36).slice(2, 10)}`;
  localStorage.setItem("copilot_user_id", id);
  return id;
}

// ── Page component ───────────────────────────────────────────

export default function CopilotPage() {
  const [input, setInput] = useState("");
  const [userMessage, setUserMessage] = useState("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [copilotStatus, setCopilotStatus] = useState<CopilotStatus>("idle");
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [isSubmittingApproval, setIsSubmittingApproval] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  // Extract application package from interrupt context if available
  const [applicationPackage, setApplicationPackage] =
    useState<ApplicationPackage | null>(null);

  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const { events, status: sseStatus, interrupt, start, abort } = useSSE();

  // ── Sync SSE status → copilot status ────────────────────────
  useEffect(() => {
    if (sseStatus === "streaming") {
      setCopilotStatus("streaming");
    } else if (sseStatus === "done") {
      setCopilotStatus((prev) =>
        prev === "awaiting-approval" ? "awaiting-approval" : "done"
      );
    } else if (sseStatus === "error") {
      setCopilotStatus("error");
    }
  }, [sseStatus]);

  // ── Handle interrupt event → open approval modal ──────────
  useEffect(() => {
    if (interrupt) {
      setCopilotStatus("awaiting-approval");
      setApprovalOpen(true);

      // Extract ApplicationPackage from interrupt context if present
      const ctx = interrupt.context;
      if (ctx && typeof ctx === "object") {
        const pkg = ctx.application_package as ApplicationPackage | undefined;
        if (pkg) setApplicationPackage(pkg);
      }
    }
  }, [interrupt]);

  // ── Submit handler ───────────────────────────────────────
  const handleSubmit = useCallback(async () => {
    const message = input.trim();
    if (!message || copilotStatus === "streaming") return;

    setStartError(null);
    setUserMessage(message);
    setInput("");
    setCopilotStatus("streaming");
    setApprovalOpen(false);
    setApplicationPackage(null);
    abort();

    try {
      const userId = getDemoUserId();
      const storedOnboarding = localStorage.getItem('career-copilot:onboarding')
      const onboarding = storedOnboarding ? JSON.parse(storedOnboarding) : {}
      const docIds: string[] = onboarding.doc_ids || onboarding.docIds || []
      const resumeText: string = onboarding.resume_text || onboarding.resumeText || ''
      const githubUsername: string = onboarding.github_username || onboarding.githubUsername || ''
      const githubToken: string = onboarding.github_token || onboarding.githubToken || ''
      const { thread_id } = await startRun(userId, message, docIds, resumeText, githubUsername, githubToken);
      setThreadId(thread_id);
      start(thread_id, { userId, message });
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to start run. Check backend.";
      setStartError(msg);
      setCopilotStatus("error");
    }
  }, [input, copilotStatus, abort, start]);

  // ── Approval decision handler ────────────────────────────
  const handleApprovalDecide = useCallback(
    async (decision: ApprovalDecision) => {
      if (!threadId) return;

      setIsSubmittingApproval(true);
      try {
        const decisionObj: Record<string, unknown> = decision.approved
          ? {
              approved: true,
              ...(decision.editedPackage
                ? { edited_package: decision.editedPackage }
                : {}),
            }
          : { approved: false };

        await resumeRun(threadId, decisionObj);

        setApprovalOpen(false);
        setApplicationPackage(null);

        if (decision.approved) {
          // Resume stream to watch post-approval nodes
          const userId = getDemoUserId();
          setCopilotStatus("streaming");
          start(threadId, { userId, message: userMessage });
        } else {
          setCopilotStatus("done");
        }
      } catch (err) {
        const msg =
          err instanceof Error ? err.message : "Failed to submit decision.";
        setStartError(msg);
        setCopilotStatus("error");
        setApprovalOpen(false);
      } finally {
        setIsSubmittingApproval(false);
      }
    },
    [threadId, start, userMessage]
  );

  const handleApprovalClose = useCallback(() => {
    if (!isSubmittingApproval) setApprovalOpen(false);
  }, [isSubmittingApproval]);

  const handleReset = useCallback(() => {
    abort();
    setInput("");
    setUserMessage("");
    setThreadId(null);
    setCopilotStatus("idle");
    setApprovalOpen(false);
    setApplicationPackage(null);
    setStartError(null);
    setTimeout(() => textareaRef.current?.focus(), 50);
  }, [abort]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSubmit =
    input.trim().length > 0 && copilotStatus !== "streaming";

  const showStream = copilotStatus !== "idle" || userMessage.length > 0;

  return (
    <>
      <Header title="Copilot" subtitle="AI career assistant" />

      <main className="flex-1 flex flex-col overflow-hidden px-6 py-6">
        <div className="max-w-4xl w-full mx-auto flex flex-col flex-1 min-h-0 gap-6">

          {/* ── Editorial page title (only on idle) ── */}
          {copilotStatus === "idle" && (
            <div className="space-y-0">
              <span className="editorial-rule" aria-hidden="true" />
              <h2
                className="font-display text-3xl font-semibold text-foreground leading-tight"
              >
                What&apos;s your career goal today?
              </h2>
              <p className="mt-2 text-muted-foreground text-sm max-w-md">
                Describe what you&apos;re looking for — the copilot will search, rank,
                tailor applications, and ask for your approval before sending
                anything.
              </p>
            </div>
          )}

          {/* ── Stream / activity area ── */}
          {showStream && (
            <div className="flex-1 min-h-0 overflow-y-auto">
              <ChatStream
                events={events}
                status={copilotStatus}
                userMessage={userMessage}
              />
            </div>
          )}

          {/* ── Start error ── */}
          {startError && (
            <div className="rounded-md bg-destructive/8 border border-destructive/20 px-4 py-3 text-sm text-destructive">
              {startError}
            </div>
          )}

          {/* ── Input area ── */}
          <div
            className={cn(
              "card-warm px-4 py-3",
              copilotStatus === "streaming" && "opacity-60 pointer-events-none"
            )}
          >
            <label htmlFor="copilot-input" className="sr-only">
              Describe your career goal
            </label>
            <textarea
              id="copilot-input"
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Find remote AI engineer roles in Europe and tailor an application…"
              rows={3}
              disabled={copilotStatus === "streaming"}
              className={cn(
                "w-full resize-none bg-transparent text-sm text-foreground",
                "placeholder:text-muted-foreground/60",
                "focus:outline-none",
                "disabled:cursor-not-allowed"
              )}
              aria-label="Career goal input"
            />
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-border">
              <p className="text-xs text-muted-foreground/50">
                Press Enter to send · Shift+Enter for new line
              </p>
              <div className="flex items-center gap-2">
                {(copilotStatus === "done" ||
                  copilotStatus === "error" ||
                  copilotStatus === "awaiting-approval") && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleReset}
                    className="gap-1.5 text-muted-foreground h-8"
                    aria-label="Start a new conversation"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    New
                  </Button>
                )}
                <Button
                  size="sm"
                  onClick={handleSubmit}
                  disabled={!canSubmit}
                  className="gap-1.5 h-8"
                  aria-label="Send message"
                >
                  <SendHorizonal className="h-3.5 w-3.5" />
                  Send
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* ── HITL Approval Modal — renders as blocking overlay ── */}
      {interrupt && (
        <ApprovalModal
          open={approvalOpen}
          hitlRequest={interrupt}
          applicationPackage={applicationPackage}
          isSubmitting={isSubmittingApproval}
          onDecide={handleApprovalDecide}
          onClose={handleApprovalClose}
        />
      )}
    </>
  );
}
