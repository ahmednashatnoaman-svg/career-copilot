"use client";

import { useCallback, useRef, useState } from "react";
import { Header } from "@/components/header";
import { ChatStream, type CopilotStatus } from "@/components/ChatStream";
import { Button } from "@/components/ui/button";
import { useSSE } from "@/lib/useSSE";
import { startRun } from "@/lib/api";
import { SendHorizonal, RefreshCw, GraduationCap } from "lucide-react";
import { cn } from "@/lib/utils";

const DEMO_USER_ID = "demo-user";

interface CoachingPageState {
  userInput: string;
  sessionId: string | null;
  coachingStatus: CopilotStatus;
  startError: string | null;
}

export default function CoachingPage() {
  const router = useRef<HTMLTextAreaElement>(null);
  const [state, setState] = useState<CoachingPageState>({
    userInput: "",
    sessionId: null,
    coachingStatus: "idle",
    startError: null,
  });

  const { events, start, abort } = useSSE();

  const handleStartMockInterview = useCallback(async () => {
    setState((s) => ({
      ...s,
      startError: null,
      coachingStatus: "streaming",
    }));

    try {
      // In production, call startRun with coaching-specific message
      const message =
        "Start a mock interview. Ask me a technical interview question and provide coaching feedback.";

      const { thread_id } = await startRun(DEMO_USER_ID, message);
      setState((s) => ({ ...s, sessionId: thread_id }));

      // Start SSE stream
      start(thread_id, {
        userId: DEMO_USER_ID,
        message,
      });
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Failed to start interview session.";
      setState((s) => ({
        ...s,
        startError: msg,
        coachingStatus: "error",
      }));
    }
  }, [start]);

  const handleSubmitResponse = useCallback(async () => {
    const response = state.userInput.trim();
    if (!response || state.coachingStatus === "streaming") return;

    setState((s) => ({
      ...s,
      userInput: "",
      coachingStatus: "streaming",
      startError: null,
    }));

    try {
      if (!state.sessionId) {
        // First response: start coaching run
        const message = `Practice question response: ${response}. Now provide feedback and ask the next question.`;
        const { thread_id } = await startRun(DEMO_USER_ID, message);
        setState((s) => ({ ...s, sessionId: thread_id }));
        start(thread_id, { userId: DEMO_USER_ID, message });
      } else {
        // Subsequent responses
        const message = `My answer: ${response}`;
        start(state.sessionId, { userId: DEMO_USER_ID, message });
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to send response.";
      setState((s) => ({
        ...s,
        startError: msg,
        coachingStatus: "error",
      }));
    }
  }, [state.userInput, state.coachingStatus, state.sessionId, start]);

  const handleReset = useCallback(() => {
    abort();
    setState({
      userInput: "",
      sessionId: null,
      coachingStatus: "idle",
      startError: null,
    });
    setTimeout(() => router.current?.focus(), 50);
  }, [abort]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmitResponse();
    }
  };

  const canSubmit =
    state.userInput.trim().length > 0 && state.coachingStatus !== "streaming";

  const showStream = state.coachingStatus !== "idle" || events.length > 0;

  // Empty state
  if (state.coachingStatus === "idle" && events.length === 0) {
    return (
      <>
        <Header
          title="Coaching"
          subtitle="Interview prep and personalised skill tips"
        />
        <main className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-3xl mx-auto space-y-8">
            {/* ── Hero section ── */}
            <div className="space-y-6 pt-4">
              <div className="space-y-1">
                <span className="editorial-rule" aria-hidden="true" />
                <h1 className="font-display text-3xl font-semibold text-foreground leading-tight">
                  Interview Coaching
                </h1>
                <p className="mt-3 text-base text-muted-foreground max-w-md">
                  Practice with AI-powered mock interviews. Get instant feedback on
                  your responses and improve your interview skills.
                </p>
              </div>

              {/* ── Cards: Features ── */}
              <div className="grid gap-4 sm:grid-cols-2 pt-6">
                <div className="card-warm px-4 py-3">
                  <p className="font-medium text-foreground text-sm mb-1">
                    Real-world questions
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Practice questions tailored to your target roles
                  </p>
                </div>
                <div className="card-warm px-4 py-3">
                  <p className="font-medium text-foreground text-sm mb-1">
                    Instant feedback
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Get coaching tips to improve your answers
                  </p>
                </div>
              </div>
            </div>

            {/* ── CTA ── */}
            <div className="pt-4 border-t border-border">
              <Button
                onClick={handleStartMockInterview}
                size="lg"
                className="gap-2"
                aria-label="Start mock interview"
              >
                <GraduationCap className="h-5 w-5" />
                Start Mock Interview
              </Button>
              <p className="mt-3 text-xs text-muted-foreground">
                You can answer as many practice questions as you like.
              </p>
            </div>
          </div>
        </main>
      </>
    );
  }

  // Active coaching session
  return (
    <>
      <Header
        title="Coaching"
        subtitle="Interview prep and personalised skill tips"
      />

      <main className="flex-1 flex flex-col overflow-hidden px-6 py-6">
        <div className="max-w-3xl w-full mx-auto flex flex-col flex-1 min-h-0 gap-6">
          {/* ── Title (on idle, before first question) ── */}
          {state.coachingStatus === "idle" && (
            <div className="space-y-0">
              <span className="editorial-rule" aria-hidden="true" />
              <h2 className="font-display text-2xl font-semibold text-foreground leading-tight">
                Let&apos;s practice together
              </h2>
              <p className="mt-2 text-muted-foreground text-sm max-w-md">
                I&apos;ll ask you interview questions and provide real-time coaching
                feedback.
              </p>
            </div>
          )}

          {/* ── Chat stream ── */}
          {showStream && (
            <div className="flex-1 min-h-0 overflow-y-auto">
              <ChatStream
                events={events}
                status={state.coachingStatus}
                userMessage={state.userInput}
              />
            </div>
          )}

          {/* ── Error banner ── */}
          {state.startError && (
            <div className="rounded-md bg-destructive/8 border border-destructive/20 px-4 py-3 text-sm text-destructive">
              {state.startError}
            </div>
          )}

          {/* ── Input area ── */}
          <div
            className={cn(
              "card-warm px-4 py-3",
              state.coachingStatus === "streaming" &&
                "opacity-60 pointer-events-none"
            )}
          >
            <label htmlFor="coaching-input" className="sr-only">
              Your response to the interview question
            </label>
            <textarea
              id="coaching-input"
              ref={router}
              value={state.userInput}
              onChange={(e) =>
                setState((s) => ({ ...s, userInput: e.target.value }))
              }
              onKeyDown={handleKeyDown}
              placeholder="Type your response here. Press Enter to submit, Shift+Enter for a new line."
              rows={4}
              disabled={state.coachingStatus === "streaming"}
              className={cn(
                "w-full resize-none bg-transparent text-sm text-foreground",
                "placeholder:text-muted-foreground/60",
                "focus:outline-none",
                "disabled:cursor-not-allowed"
              )}
              aria-label="Interview response input"
            />
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-border">
              <p className="text-xs text-muted-foreground/50">
                Press Enter to send · Shift+Enter for new line
              </p>
              <div className="flex items-center gap-2">
                {(state.coachingStatus === "done" ||
                  state.coachingStatus === "error") && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleReset}
                    className="gap-1.5 text-muted-foreground h-8"
                    aria-label="Start a new coaching session"
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                    New
                  </Button>
                )}
                <Button
                  size="sm"
                  onClick={handleSubmitResponse}
                  disabled={!canSubmit}
                  className="gap-1.5 h-8"
                  aria-label="Send your response"
                >
                  <SendHorizonal className="h-3.5 w-3.5" />
                  Send
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
