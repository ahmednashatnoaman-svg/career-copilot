"use client";

import { useRouter } from "next/navigation";
import { ArrowRight, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { RankedMatch } from "@/lib/types";
import { cn } from "@/lib/utils";

interface MatchCardProps {
  match: RankedMatch;
  onApply?: (match: RankedMatch) => void;
}

/**
 * MatchCard — renders a single job match with score and rationale.
 * Follows Editorial Career Studio design: warm card, evergreen accent, tasteful score indicator.
 */
export function MatchCard({ match, onApply }: MatchCardProps) {
  const router = useRouter();

  const handleApply = () => {
    if (onApply) {
      onApply(match);
    } else {
      // Default: route to copilot with job context
      router.push(`/copilot?job_id=${encodeURIComponent(match.job_id)}`);
    }
  };

  // Score as percentage (0-100 assumed)
  const scorePercent = Math.round(match.score * 100);
  // Visual indicator: how many "bars" (1-5) filled
  const scoreLevel = Math.ceil((match.score / 100) * 5);

  return (
    <article
      className={cn(
        "card-warm px-5 py-4 space-y-4",
        "transition-shadow hover:shadow-lg"
      )}
    >
      {/* ── Header: title, company, score ── */}
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <a
            href={match.url || "#"}
            target="_blank"
            rel="noopener noreferrer"
            className={cn(
              "font-display text-lg font-semibold text-foreground",
              "hover:text-primary transition-colors",
              match.url && "cursor-pointer"
            )}
          >
            {match.title}
          </a>
          <p className="text-sm text-muted-foreground mt-0.5">
            {match.company}
          </p>
        </div>

        {/* ── Score badge ── */}
        <div className="flex flex-col items-center gap-1.5 flex-shrink-0">
          <div
            className={cn(
              "inline-flex items-center justify-center h-10 w-10 rounded-full",
              "bg-primary/10 text-primary"
            )}
          >
            <Zap className="h-5 w-5" />
          </div>
          <p className="text-xs font-medium text-muted-foreground">
            {scorePercent}%
          </p>
        </div>
      </div>

      {/* ── Rationale (reasons why matched) ── */}
      {match.reasons && match.reasons.length > 0 && (
        <div className="pt-2 border-t border-border">
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-2">
            Why matched
          </p>
          <ul className="space-y-1.5">
            {match.reasons.map((reason, idx) => (
              <li key={idx} className="flex gap-2 text-sm text-foreground">
                <span className="text-primary flex-shrink-0 mt-0.5">•</span>
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── CTA ── */}
      <div className="flex items-center justify-between pt-2 border-t border-border">
        <p className="text-xs text-muted-foreground/70">
          Match strength: {["Very Low", "Low", "Medium", "High", "Excellent"][scoreLevel - 1]}
        </p>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleApply}
          className="gap-1.5 text-primary hover:bg-primary/5 h-8"
          aria-label={`Apply or tailor for ${match.title} at ${match.company}`}
        >
          Tailor & Apply
          <ArrowRight className="h-3.5 w-3.5" />
        </Button>
      </div>
    </article>
  );
}
