"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/header";
import { MatchCard } from "@/components/MatchCard";
import { Button } from "@/components/ui/button";
import { listMatches } from "@/lib/api";
import type { RankedMatch } from "@/lib/types";
import { Search, Sparkles } from "lucide-react";
import { getUser } from "@/lib/auth";

export default function MatchesPage() {
  const router = useRouter();
  const [matches, setMatches] = useState<RankedMatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    getUser().then((user) => {
      const userId = user?.id ?? "anonymous";
      return listMatches(userId);
    })
      .then(setMatches)
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load matches");
      })
      .finally(() => setLoading(false));
  }, []);

  const handleApplyMatch = (match: RankedMatch) => {
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

  const handleRunCopilot = () => {
    router.push("/copilot");
  };

  // Loading state
  if (loading) {
    return (
      <>
        <Header title="Job Matches" subtitle="AI-curated opportunities for your profile" />
        <main className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-3xl mx-auto">
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 py-20 text-center">
              <div className="h-8 w-8 rounded-full border-2 border-primary border-t-transparent animate-spin mb-4" />
              <p className="text-sm text-muted-foreground">Loading matches…</p>
            </div>
          </div>
        </main>
      </>
    );
  }

  // Error state
  if (error) {
    return (
      <>
        <Header title="Job Matches" subtitle="AI-curated opportunities for your profile" />
        <main className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-3xl mx-auto">
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 py-20 text-center gap-4">
              <p className="text-sm text-destructive">{error}</p>
              <Button onClick={() => window.location.reload()} variant="ghost" size="sm">Try again</Button>
            </div>
          </div>
        </main>
      </>
    );
  }

  // Empty state
  if (matches.length === 0) {
    return (
      <>
        <Header title="Job Matches" subtitle="AI-curated opportunities for your profile" />
        <main className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-3xl mx-auto">
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 py-20 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-4">
                <Search className="h-5 w-5 text-primary" />
              </div>
              <h2 className="text-lg font-semibold text-foreground">No job matches yet</h2>
              <p className="mt-1.5 text-sm text-muted-foreground max-w-xs">
                Run the Copilot to discover personalised job opportunities matched to your profile.
              </p>
              <Button onClick={handleRunCopilot} className="mt-6 gap-2" aria-label="Start Copilot to find job matches">
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
      <Header title="Job Matches" subtitle="AI-curated opportunities for your profile" />

      <main className="flex-1 overflow-y-auto">
        {/* Editorial page header */}
        <div className="border-b border-border bg-background px-8 py-10">
          <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase mb-2">
            {matches.length} Match{matches.length !== 1 ? "es" : ""} Found
          </p>
          <h1 className="font-display text-3xl font-semibold leading-tight tracking-tight text-foreground">
            Your Job Matches
          </h1>
          <span className="editorial-rule" aria-hidden="true" />
          <p className="text-base text-muted-foreground max-w-md">
            These opportunities are aligned with your skills, experience, and career goals.
            Review the matches and tailor applications in the Copilot.
          </p>
        </div>

        {/* Content area */}
        <div className="px-8 py-10">
          <div className="max-w-4xl space-y-12">
            {/* Matches section */}
            <section aria-labelledby="matches-heading">
              <div className="mb-6">
                <h2
                  id="matches-heading"
                  className="font-display text-xl font-medium text-foreground mb-1"
                >
                  Best Matches
                </h2>
                <p className="text-sm text-muted-foreground">
                  Ranked by alignment with your profile. Click Tailor &amp; Apply to customize your application.
                </p>
              </div>

              <div className="space-y-4">
                {matches.map((match) => (
                  <MatchCard key={match.job_id} match={match} onApply={handleApplyMatch} />
                ))}
              </div>
            </section>

            {/* CTA */}
            <div className="pt-6 border-t border-border">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="font-medium text-foreground mb-1">Ready to apply?</h3>
                  <p className="text-sm text-muted-foreground">
                    Let the Copilot tailor your application for each opportunity.
                  </p>
                </div>
                <Button onClick={handleRunCopilot} className="gap-2 w-full sm:w-auto" aria-label="Start Copilot to tailor applications">
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
