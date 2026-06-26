-- ══════════════════════════════════════════════════════════
--  AI Career Copilot — Supabase Schema
--  Run in: supabase.com → project → SQL Editor → New query
-- ══════════════════════════════════════════════════════════

-- NOTE: Supabase already has auth.users built-in.
-- We create a public.profiles table that mirrors auth.users.

-- ── 1. Profiles (extends Supabase auth.users) ─────────────
CREATE TABLE IF NOT EXISTS public.profiles (
  id          UUID REFERENCES auth.users(id) ON DELETE CASCADE PRIMARY KEY,
  email       TEXT,
  full_name   TEXT,
  github_username TEXT,
  is_admin    BOOLEAN DEFAULT false,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- Auto-create profile when user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (
    new.id,
    new.email,
    new.raw_user_meta_data->>'full_name'
  );
  RETURN new;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE PROCEDURE public.handle_new_user();

-- ── 2. Documents ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.documents (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  filename    TEXT NOT NULL,
  content     TEXT,
  chunks      INT DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- ── 3. Jobs ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.jobs (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  title       TEXT NOT NULL,
  company     TEXT,
  url         TEXT,
  snippet     TEXT,
  source      TEXT,  -- adzuna | tavily | linkedin
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- ── 4. Matches ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.matches (
  id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id     UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  job_id      UUID REFERENCES public.jobs(id) ON DELETE CASCADE NOT NULL,
  score       FLOAT NOT NULL,
  reasons     TEXT[],  -- array of reason strings
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- ── 5. Applications ────────────────────────────────────────
CREATE TYPE IF NOT EXISTS application_status AS ENUM (
  'DRAFT', 'APPROVED', 'SENT', 'REJECTED', 'HUMAN_REQUIRED'
);

CREATE TABLE IF NOT EXISTS public.applications (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id       UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  job_id        UUID REFERENCES public.jobs(id) ON DELETE CASCADE,
  status        application_status DEFAULT 'DRAFT' NOT NULL,
  tailored_cv   TEXT,
  cover_letter  TEXT,
  email_draft   TEXT,
  company       TEXT,
  job_title     TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER AS $$
BEGIN new.updated_at = now(); RETURN new; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER applications_updated_at
  BEFORE UPDATE ON public.applications
  FOR EACH ROW EXECUTE PROCEDURE public.set_updated_at();

-- ── 6. Runs ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.runs (
  id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id          UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  thread_id        TEXT UNIQUE NOT NULL,
  status           TEXT DEFAULT 'running',  -- running | completed | error | interrupted
  message          TEXT,
  doc_ids          TEXT[],
  resume_text      TEXT,
  github_username  TEXT,
  github_token     TEXT,
  job_description  TEXT,
  created_at       TIMESTAMPTZ DEFAULT now(),
  completed_at     TIMESTAMPTZ
);

-- ── 7. Interview Sessions ──────────────────────────────────
CREATE TABLE IF NOT EXISTS public.interview_sessions (
  id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id         UUID REFERENCES public.profiles(id) ON DELETE CASCADE NOT NULL,
  role            TEXT NOT NULL,
  interview_type  TEXT DEFAULT 'behavioral',  -- behavioral | technical | system_design
  messages        JSONB DEFAULT '[]',
  question_count  INT DEFAULT 0,
  status          TEXT DEFAULT 'active',  -- active | completed
  created_at      TIMESTAMPTZ DEFAULT now()
);

-- ── 8. Row Level Security (RLS) ────────────────────────────
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.interview_sessions ENABLE ROW LEVEL SECURITY;

-- Profiles: users can only read/update their own
CREATE POLICY "profiles: own" ON public.profiles
  FOR ALL USING (auth.uid() = id);

-- Documents: own user's only
CREATE POLICY "documents: own" ON public.documents
  FOR ALL USING (auth.uid() = user_id);

-- Matches: own user's only
CREATE POLICY "matches: own" ON public.matches
  FOR ALL USING (auth.uid() = user_id);

-- Applications: own user's only
CREATE POLICY "applications: own" ON public.applications
  FOR ALL USING (auth.uid() = user_id);

-- Runs: own user's only
CREATE POLICY "runs: own" ON public.runs
  FOR ALL USING (auth.uid() = user_id);

-- Interview sessions: own user's only
CREATE POLICY "interview_sessions: own" ON public.interview_sessions
  FOR ALL USING (auth.uid() = user_id);

-- Jobs: anyone can read (no user_id FK)
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY "jobs: read all" ON public.jobs FOR SELECT USING (true);
CREATE POLICY "jobs: service role write" ON public.jobs FOR INSERT WITH CHECK (true);

-- ── 9. Indexes for performance ─────────────────────────────
CREATE INDEX IF NOT EXISTS idx_documents_user ON public.documents(user_id);
CREATE INDEX IF NOT EXISTS idx_matches_user ON public.matches(user_id);
CREATE INDEX IF NOT EXISTS idx_matches_score ON public.matches(score DESC);
CREATE INDEX IF NOT EXISTS idx_applications_user ON public.applications(user_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON public.applications(status);
CREATE INDEX IF NOT EXISTS idx_runs_thread ON public.runs(thread_id);
CREATE INDEX IF NOT EXISTS idx_runs_user ON public.runs(user_id);
CREATE INDEX IF NOT EXISTS idx_interview_user ON public.interview_sessions(user_id);
