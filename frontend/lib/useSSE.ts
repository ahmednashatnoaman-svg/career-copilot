"use client";

/**
 * useSSE — React hook for consuming the Career Copilot SSE stream.
 *
 * This is the ONLY place in the frontend that parses the
 *   event: <type>\ndata: <json>\n\n
 * wire format.
 *
 * The underlying parser (`parseSSEFrames`) is exported as a pure function
 * so it can be unit-tested without a browser or React runtime.
 */

import { useCallback, useRef, useState } from "react";
import { API_BASE, getAuthHeaders } from "./api";
import type {
  HitlRequest,
  SSEEvent,
  SSEStatus,
  SSERawFrame,
} from "./types";

// ────────────────────────────────────────────────────────────
// Pure SSE frame parser  (unit-testable, no React dependency)
// ────────────────────────────────────────────────────────────

/**
 * Parse one or more SSE frames from a raw text chunk.
 *
 * An SSE message block ends with a double newline (\n\n).
 * A chunk arriving from the network may contain:
 *   - a partial frame (no \n\n yet) → buffered
 *   - one complete frame
 *   - multiple complete frames (split by \n\n)
 *   - a complete frame followed by a partial one
 *
 * @param buffer   Accumulated incomplete data from previous chunks
 * @param chunk    The new text chunk received from the stream
 * @returns        { frames, remaining } — parsed frames and the leftover buffer
 */
export function parseSSEFrames(
  buffer: string,
  chunk: string
): { frames: SSERawFrame[]; remaining: string } {
  const combined = buffer + chunk;
  const blocks = combined.split("\n\n");
  // The last element is either "" (if combined ended with \n\n) or a partial block
  const remaining = blocks.pop() ?? "";

  const frames: SSERawFrame[] = [];

  for (const block of blocks) {
    if (!block.trim()) continue;

    let event = "message";
    let data = "";

    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) {
        event = line.slice("event:".length).trim();
      } else if (line.startsWith("data:")) {
        data = line.slice("data:".length).trim();
      }
      // id: and retry: lines are ignored for our use-case
    }

    frames.push({ event, data });
  }

  return { frames, remaining };
}

/**
 * Convert a raw SSE frame into a typed SSEEvent.
 * Returns null if the frame can't be parsed (defensive).
 */
export function coerceSSEFrame(frame: SSERawFrame): SSEEvent | null {
  try {
    const parsed: unknown = JSON.parse(frame.data);
    const obj = parsed as Record<string, unknown>;

    switch (frame.event) {
      case "node":
        return { type: "node", node: String(obj.node ?? ""), data: obj };
      case "token":
        return { type: "token", token: String(obj.token ?? obj.content ?? "") };
      case "interrupt":
        return {
          type: "interrupt",
          hitl_request: obj.hitl_request as HitlRequest,
        };
      case "done":
        return { type: "done", result: obj };
      case "error":
        return {
          type: "error",
          message: String(obj.message ?? obj.error ?? "Unknown error"),
        };
      default:
        return null;
    }
  } catch {
    return null;
  }
}

// ────────────────────────────────────────────────────────────
// React hook
// ────────────────────────────────────────────────────────────

export interface SSEParams {
  userId: string;
  message: string;
}

export interface UseSSEReturn {
  /** All SSE events received so far (in order) */
  events: SSEEvent[];
  /** Stream lifecycle status */
  status: SSEStatus;
  /** Populated when an `interrupt` event arrives; null otherwise */
  interrupt: HitlRequest | null;
  /** Start streaming for the given thread */
  start: (threadId: string, params: SSEParams) => void;
  /** Abort the current stream */
  abort: () => void;
}

export function useSSE(): UseSSEReturn {
  const [events, setEvents] = useState<SSEEvent[]>([]);
  const [status, setStatus] = useState<SSEStatus>("idle");
  const [interrupt, setInterrupt] = useState<HitlRequest | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const abort = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
  }, []);

  const start = useCallback(
    (threadId: string, params: SSEParams) => {
      // Cancel any in-flight stream
      abort();

      setEvents([]);
      setStatus("streaming");
      setInterrupt(null);

      const controller = new AbortController();
      abortRef.current = controller;

      const url = new URL(
        `${API_BASE}/runs/${encodeURIComponent(threadId)}/stream`
      );
      url.searchParams.set("user_id", params.userId);
      url.searchParams.set("message", params.message);

      (async () => {
        try {
          const auth = await getAuthHeaders();
          const res = await fetch(url.toString(), {
            signal: controller.signal,
            headers: { Accept: "text/event-stream", ...auth },
          });

          if (!res.ok || !res.body) {
            setStatus("error");
            return;
          }

          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const { frames, remaining } = parseSSEFrames(buffer, chunk);
            buffer = remaining;

            for (const frame of frames) {
              const event = coerceSSEFrame(frame);
              if (!event) continue;

              setEvents((prev) => [...prev, event]);

              if (event.type === "interrupt") {
                setInterrupt(event.hitl_request);
              }

              if (event.type === "done" || event.type === "error") {
                setStatus(event.type === "done" ? "done" : "error");
                reader.cancel();
                return;
              }
            }
          }

          // Stream ended without explicit done frame
          setStatus((s) => (s === "streaming" ? "done" : s));
        } catch (err) {
          if ((err as Error).name !== "AbortError") {
            setStatus("error");
          }
        }
      })();
    },
    [abort]
  );

  return { events, status, interrupt, start, abort };
}
