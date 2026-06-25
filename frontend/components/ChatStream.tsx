"use client";

/**
 * ChatStream — displays the streaming agent run.
 *
 * Two panels:
 *   1. Agent Activity Rail (left/top) — node events rendered as a timeline;
 *      this is the memorable anchor of the editorial design.
 *   2. Output area (right/below) — accumulated token text.
 *
 * Status states: idle | streaming | awaiting-approval | done | error
 */

import { useEffect, useRef } from "react";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { SSEEvent, SSENodeEvent } from "@/lib/types";

export type CopilotStatus =
  | "idle"
  | "streaming"
  | "awaiting-approval"
  | "done"
  | "error";

interface ChatStreamProps {
  events: SSEEvent[];
  status: CopilotStatus;
  userMessage: string;
}

/** Friendly display names for backend node identifiers */
const NODE_LABELS: Record<string, string> = {
  job_matcher: "Matching jobs",
  resume_writer: "Tailoring resume",
  cover_letter: "Writing cover letter",
  human_approval: "Awaiting your approval",
  application_sender: "Sending application",
  coach: "Career coaching",
  search: "Searching job boards",
  ranker: "Ranking opportunities",
  planner: "Planning next steps",
};

function nodeLabel(node: string): string {
  return NODE_LABELS[node] ?? node.replace(/_/g, " ");
}

interface AgentRailItemProps {
  event: SSENodeEvent;
  index: number;
  isLast: boolean;
  status: CopilotStatus;
}

function AgentRailItem({ event, isLast, status }: AgentRailItemProps) {
  const isActive = isLast && status === "streaming";
  const isDone = !isLast || status === "done" || status === "awaiting-approval";

  return (
    <div className="flex items-start gap-3 group">
      {/* Dot + line */}
      <div className="flex flex-col items-center shrink-0">
        <div
          className={cn(
            "h-2 w-2 rounded-full mt-1.5 shrink-0 transition-colors duration-300",
            isActive
              ? "bg-primary ring-4 ring-primary/20 animate-pulse"
              : isDone
                ? "bg-primary/60"
                : "bg-border"
          )}
          aria-hidden="true"
        />
        {!isLast && (
          <div
            className="w-px flex-1 bg-border min-h-[20px] mt-1"
            aria-hidden="true"
          />
        )}
      </div>

      {/* Content */}
      <div className="pb-4 min-w-0">
        <p
          className={cn(
            "text-sm leading-tight transition-colors",
            isActive
              ? "text-foreground font-medium"
              : "text-muted-foreground"
          )}
        >
          {nodeLabel(event.node)}
        </p>
        {isActive && (
          <p className="text-xs text-muted-foreground/70 mt-0.5 flex items-center gap-1">
            <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
            Processing…
          </p>
        )}
      </div>
    </div>
  );
}

export function ChatStream({ events, status, userMessage }: ChatStreamProps) {
  const outputRef = useRef<HTMLDivElement>(null);

  const nodeEvents = events.filter(
    (e): e is SSENodeEvent => e.type === "node"
  );

  const tokenText = events
    .filter((e) => e.type === "token")
    .map((e) => (e as { type: "token"; token: string }).token)
    .join("");

  const errorMessage = events
    .filter((e) => e.type === "error")
    .map((e) => (e as { type: "error"; message: string }).message)
    .at(-1);

  // Auto-scroll output area as tokens arrive
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [tokenText]);

  if (status === "idle") return null;

  return (
    <div className="flex-1 flex flex-col min-h-0 space-y-4">
      {/* User message echo */}
      <div className="card-warm px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-1">
          Your goal
        </p>
        <p className="text-sm text-foreground leading-relaxed">{userMessage}</p>
      </div>

      {/* Main content: Rail + Output */}
      <div className="flex-1 flex flex-col lg:flex-row gap-4 min-h-0">
        {/* ── Agent Activity Rail ── */}
        <aside
          className={cn(
            "lg:w-52 xl:w-60 shrink-0",
            "card-warm px-4 py-4"
          )}
          aria-label="Agent activity timeline"
        >
          {/* Section header with editorial accent */}
          <div className="mb-4">
            <span className="block h-px w-6 bg-primary mb-2" aria-hidden="true" />
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Agent Activity
            </p>
          </div>

          {nodeEvents.length === 0 ? (
            <div className="flex items-center gap-2 text-muted-foreground/60">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              <span className="text-xs">Starting up…</span>
            </div>
          ) : (
            <div role="list" aria-label="Agent steps">
              {nodeEvents.map((event, i) => (
                <div key={`${event.node}-${i}`} role="listitem">
                  <AgentRailItem
                    event={event}
                    index={i}
                    isLast={i === nodeEvents.length - 1}
                    status={status}
                  />
                </div>
              ))}
            </div>
          )}

          {/* Status badge */}
          <div className="mt-2 pt-3 border-t border-border">
            <StatusBadge status={status} />
          </div>
        </aside>

        {/* ── Output / token stream ── */}
        <div className="flex-1 card-warm px-5 py-4 flex flex-col min-h-0 min-h-[200px]">
          <div className="mb-3">
            <span className="block h-px w-6 bg-primary mb-2" aria-hidden="true" />
            <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
              Output
            </p>
          </div>

          {status === "error" ? (
            <div className="flex items-start gap-3 rounded-md bg-destructive/8 border border-destructive/20 px-4 py-3">
              <AlertCircle
                className="h-4 w-4 text-destructive mt-0.5 shrink-0"
                aria-hidden="true"
              />
              <p className="text-sm text-destructive leading-relaxed">
                {errorMessage ?? "An unexpected error occurred. Please try again."}
              </p>
            </div>
          ) : status === "awaiting-approval" && !tokenText ? (
            <div className="flex items-start gap-3 rounded-md bg-primary/6 border border-primary/20 px-4 py-3">
              <Clock
                className="h-4 w-4 text-primary mt-0.5 shrink-0"
                aria-hidden="true"
              />
              <p className="text-sm text-primary/80 leading-relaxed">
                The agent has prepared your application and is waiting for your
                review. Check the approval dialog above.
              </p>
            </div>
          ) : tokenText ? (
            <div
              ref={outputRef}
              className="flex-1 overflow-y-auto text-sm text-foreground leading-relaxed whitespace-pre-wrap min-h-0"
              aria-live="polite"
              aria-label="Agent output"
            >
              {tokenText}
              {status === "streaming" && (
                <span
                  className="inline-block w-0.5 h-4 bg-primary/70 ml-0.5 animate-pulse align-middle"
                  aria-hidden="true"
                />
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2 text-muted-foreground/60">
              <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
              <span className="text-sm">Agent is working…</span>
            </div>
          )}

          {status === "done" && tokenText && (
            <div className="mt-3 pt-3 border-t border-border flex items-center gap-1.5 text-xs text-muted-foreground">
              <CheckCircle2 className="h-3.5 w-3.5 text-primary" aria-hidden="true" />
              Run completed
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: CopilotStatus }) {
  const config: Record<
    CopilotStatus,
    { label: string; icon: React.ReactNode; className: string }
  > = {
    idle: {
      label: "Idle",
      icon: <Clock className="h-3 w-3" />,
      className: "text-muted-foreground/60",
    },
    streaming: {
      label: "Running",
      icon: <Loader2 className="h-3 w-3 animate-spin" />,
      className: "text-primary",
    },
    "awaiting-approval": {
      label: "Awaiting you",
      icon: <Sparkles className="h-3 w-3" />,
      className: "text-amber-600 dark:text-amber-400",
    },
    done: {
      label: "Done",
      icon: <CheckCircle2 className="h-3 w-3" />,
      className: "text-primary",
    },
    error: {
      label: "Error",
      icon: <XCircle className="h-3 w-3" />,
      className: "text-destructive",
    },
  };

  const { label, icon, className } = config[status];

  return (
    <div
      className={cn("flex items-center gap-1.5 text-xs font-medium", className)}
      aria-label={`Status: ${label}`}
    >
      {icon}
      {label}
    </div>
  );
}
