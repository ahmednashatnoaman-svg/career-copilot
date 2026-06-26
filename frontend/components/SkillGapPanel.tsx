"use client";

import { BookOpen, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface SkillGap {
  skill: string;
  proficiency: "beginner" | "intermediate" | "advanced";
  importance: "critical" | "high" | "medium";
  resources?: string[];
}

interface SkillGapPanelProps {
  gaps: SkillGap[];
  title?: string;
  subtitle?: string;
  onStartLearning?: (gap: SkillGap) => void;
  className?: string;
}

/**
 * SkillGapPanel — renders missing skills with suggested learning paths.
 * Follows Editorial Career Studio: warm card, evergreen callouts, tasteful layout.
 */
export function SkillGapPanel({
  gaps,
  title = "Skill Gaps",
  subtitle = "Skills to develop for the next opportunity",
  onStartLearning,
  className,
}: SkillGapPanelProps) {
  if (!gaps || gaps.length === 0) {
    return (
      <div
        className={cn(
          "card-warm px-5 py-6 text-center",
          className
        )}
      >
        <div className="flex justify-center mb-3">
          <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
            <Target className="h-5 w-5 text-primary" />
          </div>
        </div>
        <p className="text-sm font-medium text-foreground">No skill gaps identified</p>
        <p className="text-xs text-muted-foreground mt-1">
          You&apos;re well-aligned for this opportunity.
        </p>
      </div>
    );
  }

  // Sort by importance: critical → high → medium
  const importanceOrder = { critical: 0, high: 1, medium: 2 };
  const sortedGaps = [...gaps].sort(
    (a, b) => importanceOrder[a.importance] - importanceOrder[b.importance]
  );

  return (
    <section className={cn("space-y-4", className)}>
      {/* ── Header ── */}
      <div className="space-y-1">
        <h3 className="font-display text-lg font-medium text-foreground">
          {title}
        </h3>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </div>

      {/* ── Gaps list ── */}
      <div className="space-y-3">
        {sortedGaps.map((gap, idx) => (
          <div
            key={idx}
            className={cn(
              "card-warm px-4 py-3 border-l-4",
              gap.importance === "critical"
                ? "border-l-destructive"
                : gap.importance === "high"
                  ? "border-l-primary"
                  : "border-l-accent"
            )}
          >
            {/* ── Skill header ── */}
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex-1">
                <p className="font-medium text-foreground text-sm">
                  {gap.skill}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Level: {gap.proficiency.charAt(0).toUpperCase() + gap.proficiency.slice(1)}
                  {" "}
                  <span className="text-muted-foreground/60">
                    • Importance:{" "}
                    <span
                      className={cn(
                        gap.importance === "critical"
                          ? "text-destructive font-medium"
                          : gap.importance === "high"
                            ? "text-primary font-medium"
                            : "text-accent font-medium"
                      )}
                    >
                      {gap.importance.charAt(0).toUpperCase() + gap.importance.slice(1)}
                    </span>
                  </span>
                </p>
              </div>
            </div>

            {/* ── Resources ── */}
            {gap.resources && gap.resources.length > 0 && (
              <div className="mt-2 pt-2 border-t border-border/50">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-widest mb-1.5">
                  Learning resources
                </p>
                <ul className="space-y-1">
                  {gap.resources.map((resource, ridx) => (
                    <li key={ridx} className="text-xs text-foreground/80">
                      <span className="text-primary/60 mr-1.5">→</span>
                      {resource}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* ── CTA ── */}
            {onStartLearning && (
              <div className="mt-3 pt-2 border-t border-border/50">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onStartLearning(gap)}
                  className="gap-1.5 text-primary hover:bg-primary/5 h-7 text-xs"
                  aria-label={`Start learning ${gap.skill}`}
                >
                  <BookOpen className="h-3 w-3" />
                  Start learning
                </Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
