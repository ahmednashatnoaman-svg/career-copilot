/**
 * Typed API client for the Career Copilot backend.
 * All network calls go through this module — components never call fetch directly.
 */

import type {
  ApplicationPackage,
  DocumentResponse,
  RunResponse,
} from "./types";

/**
 * Backend API base URL.
 * Set NEXT_PUBLIC_API_BASE in your environment to override.
 * Default: http://localhost:8000
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

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

  const res = await fetch(`${API_BASE}/documents`, {
    method: "POST",
    body: form,
  });

  return handleResponse<DocumentResponse>(res);
}

/**
 * Start an agent run.
 * POST /runs  (json: { user_id, message, doc_ids })
 */
export async function startRun(
  userId: string,
  message: string,
  docIds: string[] = []
): Promise<RunResponse> {
  const res = await fetch(`${API_BASE}/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, message, doc_ids: docIds }),
  });

  return handleResponse<RunResponse>(res);
}

/**
 * Resume a paused run after a human-in-the-loop decision.
 * POST /runs/{threadId}/resume  (json: { decision })
 */
export async function resumeRun(
  threadId: string,
  decision: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/runs/${encodeURIComponent(threadId)}/resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ decision }),
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

  const res = await fetch(url.toString());
  return handleResponse<ApplicationPackage[]>(res);
}
