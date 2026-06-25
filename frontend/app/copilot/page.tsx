import { Header } from "@/components/header";
import { MessageSquare } from "lucide-react";

export default function CopilotPage() {
  return (
    <>
      <Header
        title="Copilot"
        subtitle="AI career assistant"
      />
      <main className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-2xl mx-auto">
          <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border bg-muted/30 py-20 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 mb-4">
              <MessageSquare className="h-5 w-5 text-primary" />
            </div>
            <h2 className="text-lg font-semibold text-foreground">
              AI Copilot Chat
            </h2>
            <p className="mt-1.5 text-sm text-muted-foreground max-w-xs">
              Streaming chat with your AI career assistant will be implemented here.
            </p>
            <p className="mt-4 text-xs text-muted-foreground/60">
              Placeholder — Task 3
            </p>
          </div>
        </div>
      </main>
    </>
  );
}
