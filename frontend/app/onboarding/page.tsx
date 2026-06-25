"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { UploadDropzone } from "@/components/UploadDropzone";
import { Github, Target, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

const USER_ID = "demo-user";
const LS_KEY = "career-copilot:onboarding";

interface OnboardingStore {
  githubUsername: string;
  github_username?: string;
  careerGoal: string;
  doc_ids: string[];
  resume_text: string;
  github_token: string;
}

function loadStore(): OnboardingStore {
  if (typeof window === "undefined") return { githubUsername: "", careerGoal: "", doc_ids: [], resume_text: "", github_token: "" };
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : { githubUsername: "", careerGoal: "", doc_ids: [], resume_text: "", github_token: "" };
  } catch {
    return { githubUsername: "", careerGoal: "", doc_ids: [], resume_text: "", github_token: "" };
  }
}

function saveStore(data: OnboardingStore) {
  if (typeof window === "undefined") return;
  // Keep both camelCase and snake_case keys for compatibility
  localStorage.setItem(LS_KEY, JSON.stringify({ ...data, github_username: data.githubUsername }));
}

function addDocId(docId: string) {
  if (typeof window === "undefined") return;
  const current = loadStore();
  const updated = { ...current, doc_ids: [...(current.doc_ids || []), docId] };
  saveStore(updated);
}

export default function OnboardingPage() {
  const router = useRouter();
  const [githubUsername, setGithubUsername] = useState("");
  const [careerGoal, setCareerGoal] = useState("");

  // Hydrate from localStorage on mount
  useEffect(() => {
    const stored = loadStore();
    setGithubUsername(stored.githubUsername);
    setCareerGoal(stored.careerGoal);
  }, []);

  // Persist on change
  useEffect(() => {
    const current = loadStore();
    saveStore({ ...current, githubUsername, careerGoal });
  }, [githubUsername, careerGoal]);

  const handleDocUploaded = (docId: string) => {
    addDocId(docId);
  };

  const handleStart = () => {
    const current = loadStore();
    saveStore({ ...current, githubUsername, careerGoal });
    router.push("/copilot");
  };

  return (
    <main className="flex-1 overflow-y-auto">
      {/* Editorial page header */}
      <div className="border-b border-border bg-background px-8 py-10">
        <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase mb-2">
          Step 1 of 1
        </p>
        <h1 className="font-display text-4xl font-semibold leading-tight tracking-tight text-foreground">
          Set up your studio
        </h1>
        <span className="editorial-rule" aria-hidden="true" />
        <p className="text-base text-muted-foreground max-w-md">
          Upload your documents and share your goal — we&apos;ll build a
          personalised copilot around you.
        </p>
      </div>

      {/* Content */}
      <div className="px-8 py-10 max-w-2xl space-y-12">

        {/* ── Section 1: Documents ── */}
        <section aria-labelledby="docs-heading">
          <h2
            id="docs-heading"
            className="font-display text-xl font-medium text-foreground mb-1"
          >
            Your documents
          </h2>
          <p className="text-sm text-muted-foreground mb-5">
            Resume, certificates, portfolio pieces — anything you want the
            Copilot to know about.
          </p>
          <UploadDropzone userId={USER_ID} onDocUploaded={handleDocUploaded} />
        </section>

        {/* ── Section 2: Profile seed ── */}
        <section aria-labelledby="profile-heading">
          <h2
            id="profile-heading"
            className="font-display text-xl font-medium text-foreground mb-1"
          >
            Your context
          </h2>
          <p className="text-sm text-muted-foreground mb-5">
            Two signals that help the Copilot personalise every response.
          </p>

          <div className="space-y-5">
            {/* GitHub username */}
            <div>
              <label
                htmlFor="github"
                className="flex items-center gap-1.5 text-sm font-medium text-foreground mb-1.5"
              >
                <Github className="h-4 w-4 text-muted-foreground" />
                GitHub username
                <span className="text-muted-foreground font-normal">
                  (optional)
                </span>
              </label>
              <div className="relative">
                <span className="absolute inset-y-0 left-3 flex items-center text-muted-foreground text-sm select-none pointer-events-none">
                  @
                </span>
                <input
                  id="github"
                  type="text"
                  placeholder="your-handle"
                  value={githubUsername}
                  onChange={(e) => setGithubUsername(e.target.value)}
                  className={cn(
                    "w-full rounded-md border border-input bg-background py-2.5 pl-7 pr-3 text-sm",
                    "text-foreground placeholder:text-muted-foreground",
                    "focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring",
                    "transition-shadow"
                  )}
                />
              </div>
            </div>

            {/* Career goal */}
            <div>
              <label
                htmlFor="goal"
                className="flex items-center gap-1.5 text-sm font-medium text-foreground mb-1.5"
              >
                <Target className="h-4 w-4 text-muted-foreground" />
                Career goal
              </label>
              <textarea
                id="goal"
                rows={3}
                placeholder="e.g. Land a senior backend role at a climate-tech startup within 6 months"
                value={careerGoal}
                onChange={(e) => setCareerGoal(e.target.value)}
                className={cn(
                  "w-full resize-none rounded-md border border-input bg-background px-3 py-2.5 text-sm",
                  "text-foreground placeholder:text-muted-foreground",
                  "focus:outline-none focus:ring-2 focus:ring-ring focus:border-ring",
                  "transition-shadow"
                )}
              />
              <p className="mt-1 text-xs text-muted-foreground">
                Be specific — role, level, industry, timeline.
              </p>
            </div>
          </div>
        </section>

        {/* ── CTA ── */}
        <div className="pt-2 border-t border-border">
          <button
            type="button"
            onClick={handleStart}
            className={cn(
              "inline-flex items-center gap-2 rounded-md px-6 py-3",
              "bg-primary text-primary-foreground text-sm font-medium",
              "hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              "transition-colors"
            )}
          >
            Start with the Copilot
            <ArrowRight className="h-4 w-4" />
          </button>
          <p className="mt-3 text-xs text-muted-foreground">
            You can update your documents and goal at any time.
          </p>
        </div>
      </div>
    </main>
  );
}
