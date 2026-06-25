import { Header } from "@/components/header";
import { Search } from "lucide-react";

export default function MatchesPage() {
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
              Job Matches
            </h2>
            <p className="mt-1.5 text-sm text-muted-foreground max-w-xs">
              Matched job listings from the backend will be displayed here.
            </p>
            <p className="mt-4 text-xs text-muted-foreground/60">
              Placeholder — Task 4
            </p>
          </div>
        </div>
      </main>
    </>
  );
}
