// ────────────────────────────────────────────────────────────
// Shared TypeScript types mirroring backend Pydantic contracts
// ────────────────────────────────────────────────────────────

// ── Application status enum ──────────────────────────────────
export type ApplicationStatus =
  | "DRAFT"
  | "APPROVED"
  | "SENT"
  | "REJECTED"
  | "HUMAN_REQUIRED";

// ── Core domain types ────────────────────────────────────────
export interface RankedMatch {
  job_id: string;
  title: string;
  company: string;
  score: number;
  reasons: string[];
  url?: string;
}

export interface ApplicationPackage {
  application_id: string;
  user_id: string;
  job_id: string;
  title: string;
  company: string;
  status: ApplicationStatus;
  cover_letter?: string;
  resume_snapshot?: string;
  created_at: string;
  updated_at: string;
}

export interface HitlRequest {
  hitl_id: string;
  thread_id: string;
  node: string;
  question: string;
  context?: Record<string, unknown>;
  options?: string[];
}

export interface CareerPlan {
  plan_id: string;
  user_id: string;
  goals: string[];
  timeline_weeks: number;
  milestones: Array<{
    week: number;
    description: string;
    completed: boolean;
  }>;
  created_at: string;
}

// ── API response types ───────────────────────────────────────
export interface DocumentResponse {
  doc_id: string;
  chunks: number;
}

export interface RunResponse {
  run_id: string;
  thread_id: string;
}

// ── SSE event types ──────────────────────────────────────────
export type SSEEventType = "node" | "token" | "interrupt" | "done" | "error";

export interface SSENodeEvent {
  type: "node";
  node: string;
  data?: Record<string, unknown>;
}

export interface SSETokenEvent {
  type: "token";
  token: string;
}

export interface SSEInterruptEvent {
  type: "interrupt";
  hitl_request: HitlRequest;
}

export interface SSEDoneEvent {
  type: "done";
  result?: Record<string, unknown>;
}

export interface SSEErrorEvent {
  type: "error";
  message: string;
}

export type SSEEvent =
  | SSENodeEvent
  | SSETokenEvent
  | SSEInterruptEvent
  | SSEDoneEvent
  | SSEErrorEvent;

// ── SSE hook status ──────────────────────────────────────────
export type SSEStatus = "idle" | "streaming" | "done" | "error";

// ── SSE frame (raw parsed) ───────────────────────────────────
export interface SSERawFrame {
  event: string;
  data: string;
}
