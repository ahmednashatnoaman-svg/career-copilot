import Link from "next/link";
import {
  Upload,
  MessageSquare,
  Search,
  GraduationCap,
  ClipboardList,
  ArrowRight,
} from "lucide-react";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";

const routes = [
  {
    href: "/onboarding",
    label: "Onboarding",
    description: "Upload your resume and set up your profile to get started.",
    icon: Upload,
    cta: "Get started",
  },
  {
    href: "/copilot",
    label: "Copilot",
    description: "Chat with your AI career assistant for advice and strategy.",
    icon: MessageSquare,
    cta: "Open Copilot",
  },
  {
    href: "/matches",
    label: "Job Matches",
    description: "Browse AI-curated job listings matched to your profile.",
    icon: Search,
    cta: "View matches",
  },
  {
    href: "/coaching",
    label: "Coaching",
    description: "Sharpen your interview skills and get personalised tips.",
    icon: GraduationCap,
    cta: "Start coaching",
  },
  {
    href: "/applications",
    label: "Applications",
    description: "Track the status of every application in one place.",
    icon: ClipboardList,
    cta: "Track applications",
  },
];

export default function HomePage() {
  return (
    <>
      <Header
        title="Dashboard"
        subtitle="Welcome to Career Copilot"
      />
      <main className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-3xl mx-auto">
          {/* Hero */}
          <div className="mb-10">
            <h2 className="text-2xl font-bold tracking-tight text-foreground">
              Your AI-powered career companion
            </h2>
            <p className="mt-2 text-muted-foreground text-sm leading-relaxed max-w-xl">
              Upload your resume, discover matched opportunities, prep for
              interviews, and track every application — all in one place.
            </p>
          </div>

          {/* Route cards */}
          <div className="grid gap-4 sm:grid-cols-2">
            {routes.map((route) => {
              const Icon = route.icon;
              return (
                <Link
                  key={route.href}
                  href={route.href}
                  className="group flex flex-col gap-3 rounded-xl border border-border bg-card p-5 shadow-sm transition-shadow hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10">
                      <Icon className="h-4.5 w-4.5 text-primary" />
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground/40 group-hover:text-primary transition-colors mt-0.5" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-foreground text-sm">
                      {route.label}
                    </h3>
                    <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
                      {route.description}
                    </p>
                  </div>
                  <span className="text-xs font-medium text-primary">
                    {route.cta} →
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </main>
    </>
  );
}
