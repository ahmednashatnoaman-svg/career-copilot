import { Header } from "@/components/header";
import { GraduationCap } from "lucide-react";

export default function CoachingPage() {
  return (
    <>
      <Header
        title="Coaching"
        subtitle="Interview prep and personalised skill tips"
      />
      <main className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-2xl mx-auto">
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 py-20 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-4">
              <GraduationCap className="h-5 w-5 text-primary" />
            </div>
            <h2 className="text-lg font-semibold text-foreground">
              Coaching & Interview Prep
            </h2>
            <p className="mt-1.5 text-sm text-muted-foreground max-w-xs">
              AI-powered coaching sessions and interview preparation will be implemented here.
            </p>
            <p className="mt-4 text-xs text-muted-foreground/60">
              Placeholder — Task 5
            </p>
          </div>
        </div>
      </main>
    </>
  );
}
