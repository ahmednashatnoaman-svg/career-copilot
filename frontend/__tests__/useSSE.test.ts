/**
 * Unit tests for the SSE frame parser and event coercion.
 *
 * Strategy: test `parseSSEFrames` and `coerceSSEFrame` as pure functions,
 * which gives deterministic, synchronous tests with no browser/React runtime
 * needed. The hook itself wires these together — if the parsers are correct,
 * the hook is correct.
 */

import { describe, it, expect } from "vitest";
import { parseSSEFrames, coerceSSEFrame } from "../lib/useSSE";
import type { SSERawFrame } from "../lib/types";

// ── parseSSEFrames ───────────────────────────────────────────

describe("parseSSEFrames", () => {
  it("returns no frames and empty remaining for an empty input", () => {
    const { frames, remaining } = parseSSEFrames("", "");
    expect(frames).toHaveLength(0);
    expect(remaining).toBe("");
  });

  it("parses a single complete frame", () => {
    const chunk = 'event: node\ndata: {"node":"resume_writer"}\n\n';
    const { frames, remaining } = parseSSEFrames("", chunk);
    expect(frames).toHaveLength(1);
    expect(frames[0]).toEqual({ event: "node", data: '{"node":"resume_writer"}' });
    expect(remaining).toBe("");
  });

  it("buffers a partial frame (no trailing \\n\\n)", () => {
    const chunk = 'event: token\ndata: {"token":"Hello"';
    const { frames, remaining } = parseSSEFrames("", chunk);
    expect(frames).toHaveLength(0);
    expect(remaining).toBe(chunk);
  });

  it("completes a frame when the second chunk arrives", () => {
    const first = 'event: token\ndata: {"token":"Hello"';
    const second = '}\n\n';
    const { frames: f1, remaining: r1 } = parseSSEFrames("", first);
    expect(f1).toHaveLength(0);
    const { frames: f2, remaining: r2 } = parseSSEFrames(r1, second);
    expect(f2).toHaveLength(1);
    expect(f2[0]).toEqual({ event: "token", data: '{"token":"Hello"}' });
    expect(r2).toBe("");
  });

  it("parses multiple frames in a single chunk", () => {
    const chunk =
      'event: node\ndata: {"node":"a"}\n\n' +
      'event: token\ndata: {"token":"x"}\n\n' +
      'event: done\ndata: {}\n\n';
    const { frames, remaining } = parseSSEFrames("", chunk);
    expect(frames).toHaveLength(3);
    expect(frames[0].event).toBe("node");
    expect(frames[1].event).toBe("token");
    expect(frames[2].event).toBe("done");
    expect(remaining).toBe("");
  });

  it("handles multiple frames + partial tail", () => {
    const chunk =
      'event: node\ndata: {"node":"a"}\n\n' +
      'event: interrupt\ndata: {"hitl_request":';
    const { frames, remaining } = parseSSEFrames("", chunk);
    expect(frames).toHaveLength(1);
    expect(frames[0].event).toBe("node");
    expect(remaining).toBe('event: interrupt\ndata: {"hitl_request":');
  });
});

// ── coerceSSEFrame ───────────────────────────────────────────

describe("coerceSSEFrame", () => {
  it("parses a node frame", () => {
    const frame: SSERawFrame = { event: "node", data: '{"node":"cover_letter"}' };
    const event = coerceSSEFrame(frame);
    expect(event).not.toBeNull();
    expect(event?.type).toBe("node");
    if (event?.type === "node") {
      expect(event.node).toBe("cover_letter");
    }
  });

  it("parses a token frame", () => {
    const frame: SSERawFrame = { event: "token", data: '{"token":"Hello"}' };
    const event = coerceSSEFrame(frame);
    expect(event?.type).toBe("token");
    if (event?.type === "token") {
      expect(event.token).toBe("Hello");
    }
  });

  it("parses an interrupt frame and exposes hitl_request", () => {
    const hitlRequest = {
      hitl_id: "h-1",
      thread_id: "t-abc",
      node: "approval_gate",
      question: "Approve this cover letter?",
      options: ["approve", "reject"],
    };
    const frame: SSERawFrame = {
      event: "interrupt",
      data: JSON.stringify({ hitl_request: hitlRequest }),
    };
    const event = coerceSSEFrame(frame);
    expect(event?.type).toBe("interrupt");
    if (event?.type === "interrupt") {
      expect(event.hitl_request).toEqual(hitlRequest);
    }
  });

  it("parses a done frame", () => {
    const frame: SSERawFrame = { event: "done", data: '{"status":"ok"}' };
    const event = coerceSSEFrame(frame);
    expect(event?.type).toBe("done");
  });

  it("parses an error frame", () => {
    const frame: SSERawFrame = {
      event: "error",
      data: '{"message":"Something went wrong"}',
    };
    const event = coerceSSEFrame(frame);
    expect(event?.type).toBe("error");
    if (event?.type === "error") {
      expect(event.message).toBe("Something went wrong");
    }
  });

  it("returns null for unknown event types", () => {
    const frame: SSERawFrame = { event: "ping", data: "{}" };
    const event = coerceSSEFrame(frame);
    expect(event).toBeNull();
  });

  it("returns null for malformed JSON data", () => {
    const frame: SSERawFrame = { event: "node", data: "not-json" };
    const event = coerceSSEFrame(frame);
    expect(event).toBeNull();
  });
});

// ── End-to-end parser simulation (node → interrupt → done) ──

describe("SSE stream simulation: node → interrupt → done", () => {
  it("correctly sequences and exposes interrupt payload", () => {
    const hitlRequest = {
      hitl_id: "h-42",
      thread_id: "thread-xyz",
      node: "human_approval",
      question: "Send this application?",
      options: ["send", "discard"],
    };

    const rawStream =
      'event: node\ndata: {"node":"job_matcher"}\n\n' +
      'event: interrupt\ndata: ' +
      JSON.stringify({ hitl_request: hitlRequest }) +
      "\n\n" +
      'event: done\ndata: {"status":"paused_for_hitl"}\n\n';

    // Simulate streaming in two uneven chunks
    const chunk1 = rawStream.slice(0, 40);
    const chunk2 = rawStream.slice(40);

    const { frames: f1, remaining: r1 } = parseSSEFrames("", chunk1);
    const { frames: f2, remaining: r2 } = parseSSEFrames(r1, chunk2);

    expect(r2).toBe("");

    const allFrames = [...f1, ...f2];
    const allEvents = allFrames.map(coerceSSEFrame).filter(Boolean);

    // Exactly 3 events
    expect(allEvents).toHaveLength(3);
    expect(allEvents[0]?.type).toBe("node");
    expect(allEvents[1]?.type).toBe("interrupt");
    expect(allEvents[2]?.type).toBe("done");

    // Interrupt carries the hitl_request
    const interruptEvent = allEvents[1];
    if (interruptEvent?.type === "interrupt") {
      expect(interruptEvent.hitl_request).toEqual(hitlRequest);
    }

    // Status transitions simulation
    let status: "idle" | "streaming" | "done" | "error" = "idle";
    let capturedInterrupt = null;

    status = "streaming"; // stream opened

    for (const evt of allEvents) {
      if (evt?.type === "interrupt") capturedInterrupt = evt.hitl_request;
      if (evt?.type === "done") status = "done";
      if (evt?.type === "error") status = "error";
    }

    expect(status).toBe("done");
    expect(capturedInterrupt).toEqual(hitlRequest);
  });
});
