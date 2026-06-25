"use client";

import { useCallback, useRef, useState } from "react";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { coachingChat } from "@/lib/api";
import { SendHorizonal, RefreshCw, GraduationCap } from "lucide-react";
import { cn } from "@/lib/utils";
import { getUser } from "@/lib/auth";

type CoachMode = "general" | "mock_interview" | "career_plan";

interface ChatMessage {
  role: "user" | "ai";
  content: string;
}

interface CoachingState {
  messages: ChatMessage[];
  threadId: string | undefined;
  mode: CoachMode;
  userInput: string;
  loading: boolean;
  error: string | null;
  started: boolean;
}

export default function CoachingPage() {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<CoachingState>({
    messages: [],
    threadId: undefined,
    mode: "general",
    userInput: "",
    loading: false,
    error: null,
    started: false,
  });

  const scrollToBottom = () => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  const sendMessage = useCallback(async (messageText: string) => {
    if (!messageText.trim() || state.loading) return;

    setState((s) => ({
      ...s,
      userInput: "",
      loading: true,
      error: null,
      started: true,
      messages: [...s.messages, { role: "user", content: messageText }],
    }));
    scrollToBottom();

    try {
      const user = await getUser();
      const userId = user?.id ?? "anonymous";
      const result = await coachingChat(
        userId,
        messageText,
        state.threadId,
        state.mode
      );
      setState((s) => ({
        ...s,
        loading: false,
        threadId: result.thread_id,
        messages: [...s.messages, { role: "ai", content: result.response }],
      }));
      scrollToBottom();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to get response.";
      setState((s) => ({
        ...s,
        loading: false,
        error: msg,
        messages: [
          ...s.messages,
          { role: "ai", content: "Sorry, something went wrong. Please try again." },
        ],
      }));
    }
  }, [state.loading, state.threadId, state.mode]);

  const handleSubmit = useCallback(() => {
    sendMessage(state.userInput);
  }, [sendMessage, state.userInput]);

  const handleStart = useCallback(() => {
    const starters: Record<CoachMode, string> = {
      general: "Hi! I'm looking for career coaching. Can you help me?",
      mock_interview: "Let's do a mock interview. Please ask me a behavioral interview question.",
      career_plan: "I'd like help creating a career development plan. Can we get started?",
    };
    sendMessage(starters[state.mode]);
  }, [sendMessage, state.mode]);

  const handleReset = useCallback(() => {
    setState({
      messages: [],
      threadId: undefined,
      mode: state.mode,
      userInput: "",
      loading: false,
      error: null,
      started: false,
    });
    setTimeout(() => textareaRef.current?.focus(), 50);
  }, [state.mode]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSubmit = state.userInput.trim().length > 0 && !state.loading;

  const modeLabels: Record<CoachMode, string> = {
    general: "General",
    mock_interview: "Mock Interview",
    career_plan: "Career Plan",
  };

  // Empty / landing state
  if (!state.started) {
    return (
      <>
        <Header title="Coaching" subtitle="Interview prep and personalised skill tips" />
        <main className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-3xl mx-auto space-y-8">
            <div className="space-y-6 pt-4">
              <div className="space-y-1">
                <span className="editorial-rule" aria-hidden="true" />
                <h1 className="font-display text-3xl font-semibold text-foreground leading-tight">
                  Interview Coaching
                </h1>
                <p className="mt-3 text-base text-muted-foreground max-w-md">
                  Practice with AI-powered coaching. Get instant feedback and personalised career guidance.
                </p>
              </div>

              {/* Mode selector */}
              <div className="space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Session type</p>
                <div className="flex gap-2 flex-wrap">
                  {(["general", "mock_interview", "career_plan"] as CoachMode[]).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setState((s) => ({ ...s, mode: m }))}
                      className={cn(
                        "px-4 py-2 rounded-md text-sm font-medium border transition-colors",
                        state.mode === m
                          ? "bg-foreground text-background border-foreground"
                          : "border-border text-muted-foreground hover:text-foreground hover:border-foreground/40"
                      )}
                    >
                      {modeLabels[m]}
                    </button>
                  ))}
                </div>
              </div>

              {/* Feature cards */}
              <div className="grid gap-4 sm:grid-cols-2 pt-2">
                <div className="card-warm px-4 py-3">
                  <p className="font-medium text-foreground text-sm mb-1">Real-world questions</p>
                  <p className="text-xs text-muted-foreground">Practice questions tailored to your target roles</p>
                </div>
                <div className="card-warm px-4 py-3">
                  <p className="font-medium text-foreground text-sm mb-1">Instant feedback</p>
                  <p className="text-xs text-muted-foreground">Get coaching tips to improve your answers</p>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-border">
              <Button onClick={handleStart} size="lg" className="gap-2" aria-label="Start coaching session">
                <GraduationCap className="h-5 w-5" />
                Start {modeLabels[state.mode]} Session
              </Button>
              <p className="mt-3 text-xs text-muted-foreground">You can switch modes and start fresh at any time.</p>
            </div>
          </div>
        </main>
      </>
    );
  }

  // Active coaching session
  return (
    <>
      <Header title="Coaching" subtitle={modeLabels[state.mode]} />

      <main className="flex-1 flex flex-col overflow-hidden px-6 py-6">
        <div className="max-w-3xl w-full mx-auto flex flex-col flex-1 min-h-0 gap-4">

          {/* Mode tabs (compact) */}
          <div className="flex gap-2 shrink-0">
            {(["general", "mock_interview", "career_plan"] as CoachMode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setState((s) => ({ ...s, mode: m }))}
                className={cn(
                  "px-3 py-1.5 rounded-md text-xs font-medium border transition-colors",
                  state.mode === m
                    ? "bg-foreground text-background border-foreground"
                    : "border-border text-muted-foreground hover:text-foreground"
                )}
              >
                {modeLabels[m]}
              </button>
            ))}
          </div>

          {/* Chat history */}
          <div className="flex-1 min-h-0 overflow-y-auto space-y-4 py-2">
            {state.messages.map((msg, i) => (
              <div key={i} className={cn("flex", msg.role === "user" ? "justify-end" : "justify-start")}>
                <div
                  className={cn(
                    "max-w-[80%] rounded-lg px-4 py-3 text-sm",
                    msg.role === "user"
                      ? "bg-foreground text-background"
                      : "card-warm text-foreground"
                  )}
                >
                  <div className="whitespace-pre-wrap">{msg.content}</div>
                </div>
              </div>
            ))}
            {state.loading && (
              <div className="flex justify-start">
                <div className="card-warm rounded-lg px-4 py-3 text-sm text-muted-foreground animate-pulse">
                  Thinking…
                </div>
              </div>
            )}
            {state.error && (
              <div className="rounded-md bg-destructive/8 border border-destructive/20 px-4 py-3 text-sm text-destructive">
                {state.error}
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input area */}
          <div className="card-warm px-4 py-3 shrink-0">
            <label htmlFor="coaching-input" className="sr-only">
              Your message
            </label>
            <textarea
              id="coaching-input"
              ref={textareaRef}
              value={state.userInput}
              onChange={(e) => setState((s) => ({ ...s, userInput: e.target.value }))}
              onKeyDown={handleKeyDown}
              placeholder="Type your message… (Enter to send, Shift+Enter for new line)"
              rows={3}
              disabled={state.loading}
              className={cn(
                "w-full resize-none bg-transparent text-sm text-foreground",
                "placeholder:text-muted-foreground/60 focus:outline-none",
                "disabled:cursor-not-allowed disabled:opacity-60"
              )}
              aria-label="Coaching message input"
            />
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-border">
              <p className="text-xs text-muted-foreground/50">
                Enter to send · Shift+Enter for new line
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleReset}
                  className="gap-1.5 text-muted-foreground h-8"
                  aria-label="Start a new session"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  New
                </Button>
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
    </>
  );
}
