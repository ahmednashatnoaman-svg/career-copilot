/**
 * Typed API client for the Career Copilot backend.
 * All network calls go through this module — components never call fetch directly.
 *
 * Auth: each request attaches the Supabase session JWT in the Authorization header
 * so the backend middleware can verify it server-side.
 */

import type {
  ApplicationPackage,
  DocumentResponse,
  RunResponse,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

// ── Auth header helper ────────────────────────────────────────

/**
 * Returns { Authorization: "Bearer <token>" } when a Supabase session exists.
 * Returns an empty object when there is no session (public routes / server-side).
 */
export async function getAuthHeaders(): Promise<Record<string, string>> {
  try {
    const { createClient } = await import("./supabase");
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    if (token) return { Authorization: `Bearer ${token}` };
  } catch {
    // not in a browser context or Supabase unavailable
  }
  return {};
}

// ── Helper ───────────────────────────────────────────────────

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText);
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

// ── Endpoints ────────────────────────────────────────────────

/**
 * Upload a document for a user.
 * POST /documents  (multipart: user_id, file)
 */
export async function uploadDocument(
  userId: string,
  file: File
): Promise<DocumentResponse> {
  const form = new FormData();
  form.append("user_id", userId);
  form.append("file", file);

  const auth = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/documents`, {
    method: "POST",
    headers: auth,  // no Content-Type — browser sets it with boundary for FormData
    body: form,
  });

  return handleResponse<DocumentResponse>(res);
}

/**
 * Start an agent run.
 * POST /runs
 */
export async function startRun(
  userId: string,
  message: string,
  docIds: string[] = [],
  resumeText = '',
  githubUsername = '',
  githubToken = '',
): Promise<RunResponse> {
  const auth = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify({
      user_id: userId,
      message,
      doc_ids: docIds,
      resume_text: resumeText,
      github_username: githubUsername,
      github_token: githubToken,
    }),
  });

  return handleResponse<RunResponse>(res);
}

/**
 * Resume a paused run after a human-in-the-loop decision.
 * POST /runs/{threadId}/resume
 *
 * Body IS the decision object — the backend passes it directly to
 * Command(resume=decision), so do NOT nest it.
 */
export async function resumeRun(
  threadId: string,
  decision: Record<string, unknown>
): Promise<void> {
  const auth = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/runs/${encodeURIComponent(threadId)}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...auth },
    body: JSON.stringify(decision),
  });

  await handleResponse<unknown>(res);
}

/**
 * List all applications for a user.
 * GET /applications?user_id=<userId>
 */
export async function listApplications(
  userId: string
): Promise<ApplicationPackage[]> {
  const url = new URL(`${API_BASE}/applications`);
  url.searchParams.set("user_id", userId);
  const auth = await getAuthHeaders();

  const res = await fetch(url.toString(), { headers: auth });
  return handleResponse<ApplicationPackage[]>(res);
}

// ── Matches ──────────────────────────────────────────────────

import type { RankedMatch } from "./types";

/**
 * List ranked job matches for a user.
 * GET /matches?user_id=<userId>
 */
export async function listMatches(userId: string): Promise<RankedMatch[]> {
  const url = new URL(`${API_BASE}/matches`);
  url.searchParams.set('user_id', userId);
  const auth = await getAuthHeaders();
  const res = await fetch(url.toString(), { headers: auth });
  if (!res.ok) return [];
  return res.json() as Promise<RankedMatch[]>;
}

// ── Coaching chat ─────────────────────────────────────────────

export interface CoachingMessage {
  thread_id: string;
  response: string;
  mode: string;
}

/**
 * Send a message to the coaching chat endpoint.
 * POST /coaching/chat
 */
export async function coachingChat(
  userId: string,
  message: string,
  threadId?: string,
  mode = 'general',
  profile: Record<string, unknown> = {}
): Promise<CoachingMessage> {
  const auth = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/coaching/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...auth },
    body: JSON.stringify({ user_id: userId, message, thread_id: threadId, mode, profile }),
  });
  return handleResponse<CoachingMessage>(res);
}

// ── Mock interviews ───────────────────────────────────────────

export interface InterviewSession {
  session_id: string;
  question?: string;
  feedback?: string;
  question_number: number;
  status: 'active' | 'completed';
  is_complete?: boolean;
}

/**
 * Start a new mock interview session.
 * POST /interviews/start
 */
export async function startInterview(
  userId: string,
  role: string,
  interviewType = 'behavioral',
  cvSummary = ''
): Promise<InterviewSession> {
  const auth = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/interviews/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...auth },
    body: JSON.stringify({ user_id: userId, role, interview_type: interviewType, cv_summary: cvSummary }),
  });
  return handleResponse<InterviewSession>(res);
}

/**
 * Submit an answer to an interview question.
 * POST /interviews/{sessionId}/answer
 */
export async function answerInterview(sessionId: string, answer: string): Promise<InterviewSession> {
  const auth = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/interviews/${encodeURIComponent(sessionId)}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...auth },
    body: JSON.stringify({ answer }),
  });
  return handleResponse<InterviewSession>(res);
}

// ── CV Tailoring ──────────────────────────────────────────────

export interface TailoredCV {
  tailored_cv: string;
  original_cv: string;
  match_score: number;
  job_title: string;
  company: string;
}

/**
 * Tailor a CV for a specific job description.
 * POST /cv/tailor
 */
export async function tailorCV(
  userId: string,
  resumeText: string,
  jobDescription: string,
  jobTitle = '',
  company = ''
): Promise<TailoredCV> {
  const auth = await getAuthHeaders();
  const res = await fetch(`${API_BASE}/cv/tailor`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...auth },
    body: JSON.stringify({ user_id: userId, resume_text: resumeText, job_description: jobDescription, job_title: jobTitle, company }),
  });
  return handleResponse<TailoredCV>(res);
}
