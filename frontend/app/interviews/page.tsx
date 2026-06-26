"use client";

import { useState } from "react";
import { startInterview, answerInterview } from "@/lib/api";
import type { InterviewSession } from "@/lib/types";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { getUser } from "@/lib/auth";

type Phase = "setup" | "active" | "complete";
type InterviewType = "behavioral" | "technical" | "system_design";

interface ChatMessage {
  role: "ai" | "user";
  content: string;
}

const TYPE_LABELS: Record<InterviewType, string> = {
  behavioral: "Behavioral",
  technical: "Technical",
  system_design: "System Design",
};

export default function InterviewsPage() {
  const [phase, setPhase] = useState<Phase>("setup");
  const [role, setRole] = useState("");
  const [interviewType, setInterviewType] = useState<InterviewType>("behavioral");
  const [session, setSession] = useState<InterviewSession | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    if (!role.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const user = await getUser();
      const userId = user?.id ?? "anonymous";
      const result = await startInterview(userId, role, interviewType);
      setSession(result);
      setMessages([{ role: "ai", content: result.question || "Let's begin. Please answer the question above." }]);
      setPhase("active");
    } catch {
      setError("Failed to start interview. Check the backend is running.");
    } finally {
      setLoading(false);
    }
  }

  async function handleAnswer() {
    if (!answer.trim() || !session) return;
    const userAnswer = answer;
    setAnswer("");
    setMessages((prev) => [...prev, { role: "user", content: userAnswer }]);
    setLoading(true);
    try {
      const result = await answerInterview(session.session_id, userAnswer);
      setSession(result);
      const aiContent = result.feedback || result.question || "";
      if (aiContent) {
        setMessages((prev) => [...prev, { role: "ai", content: aiContent }]);
      }
      if (result.is_complete || result.status === "completed") {
        setPhase("complete");
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: "Interview service unavailable. Please try again." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAnswer();
    }
  }

  function handleReset() {
    setPhase("setup");
    setSession(null);
    setMessages([]);
    setAnswer("");
    setError(null);
    setRole("");
  }

  // SETUP PHASE
  if (phase === "setup") {
    return (
      <>
        <Header title="Mock Interview" subtitle="Practice with AI" />
        <main className="flex-1 flex flex-col items-center justify-center px-6 py-12">
          <div className="w-full max-w-md space-y-8">
            <div className="space-y-1">
              <span className="editorial-rule" aria-hidden="true" />
              <h2 className="font-display text-3xl font-semibold text-foreground">
                Prepare for your interview
              </h2>
              <p className="text-sm text-muted-foreground mt-2">
                5 questions, real-time feedback, scored responses
              </p>
            </div>
            <div className="space-y-5">
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">
                  Target Role
                </label>
                <input
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleStart(); }}
                  placeholder="e.g. Senior Software Engineer"
                  className="w-full px-3 py-2 bg-transparent border border-border rounded-md text-sm text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:ring-1 focus:ring-foreground/20"
                />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground uppercase tracking-wide block mb-1.5">
                  Interview Type
                </label>
                <div className="flex gap-2 flex-wrap">
                  {(["behavioral", "technical", "system_design"] as InterviewType[]).map((type) => (
                    <button
                      key={type}
                      type="button"
                      onClick={() => setInterviewType(type)}
                      className={cn(
                        "px-3 py-1.5 rounded-md text-xs font-medium border transition-colors",
                        interviewType === type
                          ? "bg-foreground text-background border-foreground"
                          : "border-border text-muted-foreground hover:text-foreground hover:border-foreground/40"
                      )}
                    >
                      {TYPE_LABELS[type]}
                    </button>
                  ))}
                </div>
              </div>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <Button
                onClick={handleStart}
                disabled={!role.trim() || loading}
                className="w-full"
              >
                {loading ? "Starting…" : "Start Interview"}
              </Button>
            </div>
          </div>
        </main>
      </>
    );
  }

  // ACTIVE + COMPLETE PHASES
  const questionNumber = session?.question_number ?? 1;

  return (
    <>
      <Header
        title="Mock Interview"
        subtitle={
          phase === "complete"
            ? "Interview complete"
            : `Question ${questionNumber} of 5`
        }
      />
      <main className="flex-1 flex flex-col overflow-hidden px-6 py-6">
        <div className="max-w-3xl w-full mx-auto flex flex-col flex-1 min-h-0 gap-4">

          {/* Role / type badge */}
          <div className="flex items-center gap-2 shrink-0">
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{role}</span>
            <span className="text-muted-foreground/30">·</span>
            <span className="text-xs text-muted-foreground">{TYPE_LABELS[interviewType]}</span>
          </div>

          {/* Chat history */}
          <div className="flex-1 min-h-0 overflow-y-auto space-y-4 py-2">
            {messages.map((msg, i) => (
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
            {loading && (
              <div className="flex justify-start">
                <div className="card-warm rounded-lg px-4 py-3 text-sm text-muted-foreground animate-pulse">
                  Evaluating…
                </div>
              </div>
            )}
          </div>

          {/* Answer input (active phase only) */}
          {phase === "active" && (
            <div className="card-warm px-4 py-3 shrink-0">
              <label htmlFor="answer-input" className="sr-only">Your answer</label>
              <textarea
                id="answer-input"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Type your answer… (Enter to send)"
                rows={3}
                disabled={loading}
                className={cn(
                  "w-full resize-none bg-transparent text-sm text-foreground",
                  "placeholder:text-muted-foreground/60 focus:outline-none",
                  "disabled:cursor-not-allowed disabled:opacity-60"
                )}
              />
              <div className="flex justify-end mt-2 pt-2 border-t border-border">
                <Button
                  size="sm"
                  onClick={handleAnswer}
                  disabled={!answer.trim() || loading}
                >
                  Answer
                </Button>
              </div>
            </div>
          )}

          {/* Complete state */}
          {phase === "complete" && (
            <div className="text-center py-4 space-y-4 shrink-0">
              <div className="space-y-1">
                <p className="text-sm font-medium text-foreground">Interview complete!</p>
                <p className="text-xs text-muted-foreground">Review the feedback in the conversation above.</p>
              </div>
              <Button onClick={handleReset}>Start New Interview</Button>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
