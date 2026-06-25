"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/header";
import { ApplicationRow } from "@/components/ApplicationRow";
import { Button } from "@/components/ui/button";
import { listApplications } from "@/lib/api";
import type { ApplicationPackage } from "@/lib/types";
import { ClipboardList, Sparkles, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const USER_ID = "demo-user";

export default function ApplicationsPage() {
  const router = useRouter();
  const [applications, setApplications] = useState<ApplicationPackage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchApplications = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await listApplications(USER_ID);
        setApplications(data);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load applications"
        );
      } finally {
        setLoading(false);
      }
    };

    fetchApplications();
  }, []);

  const handleRunCopilot = () => {
    router.push("/copilot");
  };

  // Loading state
  if (loading) {
    return (
      <>
        <Header title="Applications" subtitle="Track and manage your job applications" />
        <main className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-3xl mx-auto space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="card-warm px-4 py-4 animate-pulse flex items-center gap-4">
                <div className="h-4 w-2/5 bg-muted-foreground/10 rounded" />
                <div className="h-4 w-1/5 bg-muted-foreground/10 rounded" />
                <div className="ml-auto h-4 w-1/6 bg-muted-foreground/10 rounded" />
              </div>
            ))}
          </div>
        </main>
      </>
    );
  }

  // Empty state
  if (!loading && applications.length === 0 && !error) {
    return (
      <>
        <Header
          title="Applications"
          subtitle="Track and manage your job applications"
        />
        <main className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-3xl mx-auto">
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 py-20 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-4">
                <ClipboardList className="h-5 w-5 text-primary" />
              </div>
              <h2 className="text-lg font-semibold text-foreground">
                No applications yet
              </h2>
              <p className="mt-1.5 text-sm text-muted-foreground max-w-xs">
                Run the Copilot to draft your first application.
              </p>
              <Button
                onClick={handleRunCopilot}
                className="mt-6 gap-2"
                aria-label="Start Copilot to create applications"
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

  // Error state
  if (error) {
    return (
      <>
        <Header
          title="Applications"
          subtitle="Track and manage your job applications"
        />
        <main className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-3xl mx-auto">
            <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-red-50 dark:bg-red-950/20 py-20 text-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/40 mb-4">
                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
              </div>
              <h2 className="text-lg font-semibold text-red-900 dark:text-red-200">
                Something went wrong
              </h2>
              <p className="mt-1.5 text-sm text-red-700 dark:text-red-300 max-w-xs">
                {error}
              </p>
              <Button
                onClick={() => window.location.reload()}
                className="mt-6"
              >
                Try Again
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
        title="Applications"
        subtitle="Track and manage your job applications"
      />

      <main className="flex-1 overflow-y-auto">
        {/* ── Editorial page header ── */}
        <div className="border-b border-border bg-background px-8 py-10">
          <p className="text-xs font-medium tracking-widest text-muted-foreground uppercase mb-2">
            {applications.length} Application{applications.length !== 1 ? "s" : ""}
          </p>
          <h1 className="font-display text-3xl font-semibold leading-tight tracking-tight text-foreground">
            Your Applications
          </h1>
          <span className="editorial-rule" aria-hidden="true" />
          <p className="text-base text-muted-foreground max-w-md">
            Track the status of your tailored applications and review generated
            cover letters.
          </p>
        </div>

        {/* ── Content area ── */}
        <div className="px-8 py-10">
          <div className="max-w-4xl">
            {/* ── Applications list ── */}
            <section aria-labelledby="applications-heading">
              <div className="mb-6">
                <h2
                  id="applications-heading"
                  className="font-display text-xl font-medium text-foreground mb-1"
                >
                  All Applications
                </h2>
                <p className="text-sm text-muted-foreground">
                  Click "View" to see the generated cover letter for each application.
                </p>
              </div>

              {/* ── Table/List header ── */}
              <div className="hidden sm:grid sm:grid-cols-12 gap-4 px-4 py-3 border-b border-border bg-muted/50 text-xs font-medium text-muted-foreground uppercase tracking-wide rounded-t-md">
                <div className="col-span-5">Company & Role</div>
                <div className="col-span-4">Status</div>
                <div className="col-span-3 text-right">Action</div>
              </div>

              {/* ── Application rows ── */}
              <div className="border border-border rounded-md overflow-hidden">
                {applications.length > 0 ? (
                  applications.map((app) => (
                    <ApplicationRow
                      key={app.application_id}
                      application={app}
                    />
                  ))
                ) : (
                  <div className="px-4 py-8 text-center text-muted-foreground">
                    No applications found.
                  </div>
                )}
              </div>
            </section>

            {/* ── CTA ── */}
            {applications.length > 0 && (
              <div className="mt-12 pt-6 border-t border-border">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h3 className="font-medium text-foreground mb-1">
                      Ready to apply to more roles?
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Use the Copilot to tailor applications for additional opportunities.
                    </p>
                  </div>
                  <Button
                    onClick={handleRunCopilot}
                    className="gap-2 w-full sm:w-auto"
                    aria-label="Start Copilot to create more applications"
                  >
                    <Sparkles className="h-4 w-4" />
                    Create More
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </>
  );
}
