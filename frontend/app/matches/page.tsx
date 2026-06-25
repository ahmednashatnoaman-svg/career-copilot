"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Header } from "@/components/header";
import { MatchCard } from "@/components/MatchCard";
import { SkillGapPanel, type SkillGap } from "@/components/SkillGapPanel";
import { Search, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { RankedMatch } from "@/lib/types";

/**
 * Demo data — in production, this comes from a completed copilot run's state.
 * For now, render from props/local state with graceful empty state.
 */
const DEMO_MATCHES: RankedMatch[] = [
  {
    job_id: "j-001",
    title: "Senior Full Stack Engineer",
    company: "TechCorp AI",
    score: 0.92,
    reasons: [
      "5+ years experience matches requirement",
      "React expertise aligns with stack",
      "Climate tech background is a plus",
    ],
    url: "https://example.com/job/001",
  },
  {
    job_id: "j-002",
    title: "AI/ML Engineer",
    company: "DataFlow Systems",
    score: 0.87,
    reasons: [
      "Strong ML background demonstrated in projects",
      "Python and TensorFlow experience",
      "Data engineering skillset is relevant",
    ],
    url: "https://example.com/job/002",
  },
  {
    job_id: "j-003",
    title: "Product Engineer",
    company: "StartupXYZ",
    score: 0.79,
    reasons: [
      "Full stack capabilities valuable",
      "Early-stage company energy fits profile",
      "Leadership experience relevant",
    ],
    url: "https://example.com/job/003",
  },
];

const DEMO_SKILL_GAPS: SkillGap[] = [
  {
    skill: "Kubernetes",
    proficiency: "beginner",
    importance: "critical",
    resources: [
      "Kubernetes Official Tutorial",
      "Linux Academy K8s Course",
      "Practice: minikube local setup",
    ],
  },
  {
    skill: "GraphQL",
    proficiency: "intermediate",
    importance: "high",
    resources: [
      "Apollo GraphQL Docs",
      "How to GraphQL Tutorial",
      "Real-world project implementation",
    ],
  },
  {
    skill: "System Design",
    proficiency: "intermediate",
    importance: "medium",
    resources: [
      "Designing Data-Intensive Applications",
      "System Design Interview Course",
    ],
  },
];

interface MatchesPageState {
  showSkillGaps: boolean;
  selectedMatchId: string | null;
}

export default function MatchesPage() {
  const router = useRouter();
  const [state, setState] = useState<MatchesPageState>({
    showSkillGaps: false,
    selectedMatchId: null,
  });

  // Check if data is available (from a completed run)
  const hasMatches = DEMO_MATCHES.length > 0;
  const hasSkillGaps = DEMO_SKILL_GAPS.length > 0;

  const handleApplyMatch = (match: RankedMatch) => {
    // Store match context and route to copilot for tailoring
    sessionStorage.setItem(
      "copilot:match-context",
      JSON.stringify({
        job_id: match.job_id,
        job_title: match.title,
        company: match.company,
      })
    );
    router.push("/copilot");
  };

  const handleStartLearning = (gap: SkillGap) => {
    // In the future, route to learning module or coaching session
    console.log("Start learning:", gap.skill);
  };

  const handleRunCopilot = () => {
    router.push("/copilot");
  };

  // Empty state
  if (!hasMatches) {
    return (
      <>
        <Header
          title="Job Matches"
          subtitle="AI-curated opportunities for your profile"
        />
        <main className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-3xl mx-auto">
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 py-20 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-4">
                <Search className="h-5 w-5 text-primary" />
              </div>
              <h2 className="text-lg font-semibold text-foreground">
                No job matches yet
              </h2>
              <p className="mt-1.5 text-sm text-muted-foreground max-w-xs">
                Run the Copilot to discover personalised job opportunities
                matched to your profile.
              </p>
              <Button
                onClick={handleRunCopilot}
                className="mt-6 gap-2"
                aria-label="Start Copilot to find job matches"
              >
                <Sparkles className="h-4 w-4" />
                Run the Copilot
              </Button>
            </div>
          </div>
        </main>
      </>
    );
  }

  // Populated state
  return (
    <>
      <Header
        title="Job Matches"
        subtitle="AI-curated opportunities for your profile"
      />

      <main className="flex-1 overflow-y-auto">
        {/* ── Editorial page header ── */}
        <div className="border-b border-border bg-background px-8 py-10">
          <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase mb-2">
            {hasMatches && `${DEMO_MATCHES.length} Matches Found`}
          </p>
          <h1 className="font-display text-3xl font-semibold leading-tight tracking-tight text-foreground">
            Your Job Matches
          </h1>
          <span className="editorial-rule" aria-hidden="true" />
          <p className="text-base text-muted-foreground max-w-md">
            These opportunities are aligned with your skills, experience, and
            career goals. Review the matches and tailor applications in the
            Copilot.
          </p>
        </div>

        {/* ── Content area ── */}
        <div className="px-8 py-10">
          <div className="max-w-4xl space-y-12">
            {/* ── Matches section ── */}
            <section aria-labelledby="matches-heading">
              <div className="mb-6">
                <h2
                  id="matches-heading"
                  className="font-display text-xl font-medium text-foreground mb-1"
                >
                  Best Matches
                </h2>
                <p className="text-sm text-muted-foreground">
                  Ranked by alignment with your profile. Click Tailor & Apply
                  to customize your application.
                </p>
              </div>

              <div className="space-y-4">
                {DEMO_MATCHES.map((match) => (
                  <MatchCard
                    key={match.job_id}
                    match={match}
                    onApply={handleApplyMatch}
                  />
                ))}
              </div>
            </section>

            {/* ── Skill Gaps section ── */}
            {hasSkillGaps && (
              <section aria-labelledby="gaps-heading">
                <div id="gaps-heading" className="sr-only">
                  Skill Gaps
                </div>
                <SkillGapPanel
                  gaps={DEMO_SKILL_GAPS}
                  title="Skill Development"
                  subtitle="Skills that would strengthen your candidacy for these roles"
                  onStartLearning={handleStartLearning}
                />
              </section>
            )}

            {/* ── CTA ── */}
            <div className="pt-6 border-t border-border">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="font-medium text-foreground mb-1">
                    Ready to apply?
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Let the Copilot tailor your application for each opportunity.
                  </p>
                </div>
                <Button
                  onClick={handleRunCopilot}
                  className="gap-2 w-full sm:w-auto"
                  aria-label="Start Copilot to tailor applications"
                >
                  <Sparkles className="h-4 w-4" />
                  Tailor Applications
                </Button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </>
  );
}
