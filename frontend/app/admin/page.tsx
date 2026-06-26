"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Database,
  Users,
  Briefcase,
  FileText,
  CheckSquare,
  RefreshCw,
  Brain,
  Trash2,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  CheckCircle,
} from "lucide-react";
import { Header } from "@/components/header";
import { Button } from "@/components/ui/button";
import { API_BASE, getAuthHeaders } from "@/lib/api";

const ADMIN_EMAIL =
  process.env.NEXT_PUBLIC_ADMIN_EMAIL ?? "ahmed.nashat.noaman@gmail.com";

interface SystemStats {
  db_connected: boolean;
  counts: {
    users: number;
    jobs: number;
    matches: number;
    applications: number;
    documents: number;
  };
}

interface UserMemory {
  user_id: string;
  facts: Record<string, unknown>;
  count: number;
}

function StatCard({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number | string;
  icon: React.ElementType;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
      <div className="flex items-start justify-between mb-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10">
          <Icon className="h-4 w-4 text-primary" />
        </div>
        <span className="text-2xl font-bold text-foreground">
          {value === -1 ? "—" : value}
        </span>
      </div>
      <p className="text-xs text-muted-foreground font-medium uppercase tracking-wide">
        {label}
      </p>
    </div>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  const [stats, setStats] = useState<SystemStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [statsError, setStatsError] = useState<string | null>(null);

  const [memoryUserId, setMemoryUserId] = useState("");
  const [memory, setMemory] = useState<UserMemory | null>(null);
  const [loadingMemory, setLoadingMemory] = useState(false);
  const [memoryError, setMemoryError] = useState<string | null>(null);
  const [memoryExpanded, setMemoryExpanded] = useState(false);

  const [deletingKey, setDeletingKey] = useState<string | null>(null);

  const fetchStats = async () => {
    setLoadingStats(true);
    setStatsError(null);
    try {
      const auth = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/admin/stats`, { headers: auth });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setStats(await res.json());
    } catch (err) {
      setStatsError(err instanceof Error ? err.message : "Failed to load stats");
    } finally {
      setLoadingStats(false);
    }
  };

  const fetchMemory = async () => {
    if (!memoryUserId.trim()) return;
    setLoadingMemory(true);
    setMemoryError(null);
    try {
      const auth = await getAuthHeaders();
      const res = await fetch(
        `${API_BASE}/admin/memory/${encodeURIComponent(memoryUserId.trim())}`,
        { headers: auth }
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setMemory(await res.json());
      setMemoryExpanded(true);
    } catch (err) {
      setMemoryError(err instanceof Error ? err.message : "Failed to load memory");
    } finally {
      setLoadingMemory(false);
    }
  };

  const deleteMemoryKey = async (key: string) => {
    if (!memory) return;
    setDeletingKey(key);
    try {
      const auth = await getAuthHeaders();
      const res = await fetch(
        `${API_BASE}/admin/memory/${encodeURIComponent(memory.user_id)}/${encodeURIComponent(key)}`,
        { method: "DELETE", headers: auth }
      );
      if (!res.ok) throw new Error(`${res.status}`);
      setMemory((prev) => {
        if (!prev) return null;
        const updated = { ...prev.facts };
        delete updated[key];
        return { ...prev, facts: updated, count: prev.count - 1 };
      });
    } catch {
      // silent — user can retry
    } finally {
      setDeletingKey(null);
    }
  };

  // Gate: verify session email before rendering anything
  useEffect(() => {
    (async () => {
      try {
        const { createClient } = await import("@/lib/supabase");
        const supabase = createClient();
        const { data } = await supabase.auth.getSession();
        const email = data.session?.user?.email ?? "";
        if (email !== ADMIN_EMAIL) {
          router.replace("/");
          return;
        }
        setIsAdmin(true);
        fetchStats();
      } catch {
        router.replace("/");
      }
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (isAdmin === null) return null; // still checking

  return (
    <>
      <Header title="Admin" subtitle="System overview and diagnostics" />

      <main className="flex-1 overflow-y-auto px-6 py-8">
        <div className="max-w-4xl mx-auto space-y-10">

          {/* ── System Stats ────────────────────────────── */}
          <section aria-labelledby="stats-heading">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 id="stats-heading" className="text-base font-semibold text-foreground">
                  System Stats
                </h2>
                {stats && (
                  <p className="text-xs text-muted-foreground mt-0.5 flex items-center gap-1.5">
                    {stats.db_connected ? (
                      <>
                        <CheckCircle className="h-3 w-3 text-green-500" />
                        Supabase connected
                      </>
                    ) : (
                      <>
                        <AlertCircle className="h-3 w-3 text-yellow-500" />
                        In-memory fallback (no Supabase)
                      </>
                    )}
                  </p>
                )}
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchStats}
                disabled={loadingStats}
                className="gap-1.5"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${loadingStats ? "animate-spin" : ""}`} />
                Refresh
              </Button>
            </div>

            {statsError ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
                {statsError}
              </div>
            ) : loadingStats ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="rounded-xl border border-border bg-card p-5 h-24 animate-pulse" />
                ))}
              </div>
            ) : stats ? (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <StatCard label="Users" value={stats.counts.users} icon={Users} />
                <StatCard label="Jobs" value={stats.counts.jobs} icon={Briefcase} />
                <StatCard label="Matches" value={stats.counts.matches} icon={CheckSquare} />
                <StatCard label="Applications" value={stats.counts.applications} icon={FileText} />
                <StatCard label="Documents" value={stats.counts.documents} icon={Database} />
              </div>
            ) : null}
          </section>

          {/* ── Agent Memory Inspector ───────────────────── */}
          <section aria-labelledby="memory-heading">
            <h2 id="memory-heading" className="text-base font-semibold text-foreground mb-4">
              Long-term Memory Inspector
            </h2>
            <p className="text-xs text-muted-foreground mb-4">
              Inspect and manage the key-value facts stored in PostgresStore for any user.
            </p>

            <div className="flex gap-2">
              <input
                type="text"
                value={memoryUserId}
                onChange={(e) => setMemoryUserId(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && fetchMemory()}
                placeholder="Enter user ID (UUID)…"
                className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring placeholder:text-muted-foreground/60"
              />
              <Button
                onClick={fetchMemory}
                disabled={loadingMemory || !memoryUserId.trim()}
                size="sm"
                className="gap-1.5 shrink-0"
              >
                <Brain className="h-3.5 w-3.5" />
                {loadingMemory ? "Loading…" : "Inspect"}
              </Button>
            </div>

            {memoryError && (
              <p className="mt-2 text-sm text-destructive">{memoryError}</p>
            )}

            {memory && (
              <div className="mt-4 rounded-xl border border-border bg-card overflow-hidden">
                <button
                  className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-foreground hover:bg-muted/30 transition-colors"
                  onClick={() => setMemoryExpanded((v) => !v)}
                >
                  <span className="flex items-center gap-2">
                    <Brain className="h-4 w-4 text-primary" />
                    {memory.user_id.slice(0, 8)}…
                    <span className="text-xs text-muted-foreground">
                      ({memory.count} fact{memory.count !== 1 ? "s" : ""})
                    </span>
                  </span>
                  {memoryExpanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>

                {memoryExpanded && (
                  <div className="border-t border-border divide-y divide-border">
                    {Object.keys(memory.facts).length === 0 ? (
                      <p className="px-4 py-6 text-sm text-muted-foreground text-center">
                        No facts stored for this user.
                      </p>
                    ) : (
                      Object.entries(memory.facts).map(([key, value]) => (
                        <div
                          key={key}
                          className="flex items-center justify-between px-4 py-3 gap-3"
                        >
                          <div className="min-w-0">
                            <p className="text-xs font-medium text-foreground">{key}</p>
                            <p className="text-xs text-muted-foreground truncate">
                              {typeof value === "string" ? value : JSON.stringify(value)}
                            </p>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteMemoryKey(key)}
                            disabled={deletingKey === key}
                            className="shrink-0 h-7 w-7 p-0 hover:text-destructive"
                            aria-label={`Delete fact ${key}`}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </section>

          {/* ── API Quick Links ──────────────────────────── */}
          <section aria-labelledby="links-heading">
            <h2 id="links-heading" className="text-base font-semibold text-foreground mb-4">
              API Quick Links
            </h2>
            <div className="grid gap-2 sm:grid-cols-2">
              {[
                { label: "Health check", path: "/health" },
                { label: "Admin stats", path: "/admin/stats" },
                { label: "OpenAPI docs", path: "/docs" },
                { label: "ReDoc", path: "/redoc" },
              ].map(({ label, path }) => (
                <a
                  key={path}
                  href={`${API_BASE}${path}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center justify-between rounded-lg border border-border bg-card px-4 py-2.5 text-sm text-foreground hover:bg-muted/30 transition-colors"
                >
                  <span>{label}</span>
                  <span className="text-xs text-muted-foreground font-mono">{path}</span>
                </a>
              ))}
            </div>
          </section>
        </div>
      </main>
    </>
  );
}
