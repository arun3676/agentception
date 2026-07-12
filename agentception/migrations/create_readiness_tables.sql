-- ============================================================
-- AI Career Hub — Readiness Engine Tables
-- Run this in the Supabase SQL Editor (Dashboard → SQL Editor)
-- ============================================================

-- 0. Enable UUID extension (usually already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users table (if not already created by Supabase Auth)
CREATE TABLE IF NOT EXISTS public.users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT UNIQUE,
  display_name  TEXT,
  current_role  TEXT,
  target_role   TEXT,
  location_preference TEXT,
  skills_json   JSONB DEFAULT '[]'::jsonb,
  resume_token  TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- 2. Resumes table
CREATE TABLE IF NOT EXISTS public.resumes (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES public.users(id) ON DELETE CASCADE,
  resume_token    TEXT UNIQUE,
  original_text   TEXT,
  parsed_data     JSONB,
  insights        JSONB,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 3. Readiness audits — stores each audit run
CREATE TABLE IF NOT EXISTS public.readiness_audits (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES public.users(id) ON DELETE SET NULL,
  target_role   TEXT NOT NULL,
  resume_token  TEXT,
  jd_count      INTEGER,
  verdict_text  TEXT,
  gap_type      TEXT CHECK (gap_type IN ('skills', 'framing', 'ready')),
  gap_details   JSONB,
  strengths     JSONB,
  percentile    INTEGER,
  raw_audit     JSONB,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- 4. One-thing actions — the single action generated from audit
CREATE TABLE IF NOT EXISTS public.one_thing_actions (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_id      UUID REFERENCES public.readiness_audits(id) ON DELETE CASCADE,
  action_type   TEXT CHECK (action_type IN ('learn_module', 'reframe_bullet', 'apply_now')),
  action_data   JSONB,
  deadline_days INTEGER,
  completed     BOOLEAN DEFAULT false,
  completed_at  TIMESTAMPTZ,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- 5. Application outcomes — the feedback loop
CREATE TABLE IF NOT EXISTS public.application_outcomes (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID REFERENCES public.users(id) ON DELETE SET NULL,
  audit_id          UUID REFERENCES public.readiness_audits(id) ON DELETE SET NULL,
  company           TEXT,
  role              TEXT,
  applied_at        TIMESTAMPTZ,
  outcome           TEXT CHECK (outcome IN ('ghosted','rejected','screen','onsite','offer')),
  outcome_logged_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Learning paths (Supabase version)
CREATE TABLE IF NOT EXISTS public.learning_paths (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID REFERENCES public.users(id) ON DELETE SET NULL,
  title           TEXT,
  topic           TEXT,
  expertise_level TEXT,
  target_role     TEXT,
  path_data       JSONB NOT NULL DEFAULT '{}'::jsonb,
  is_archived     BOOLEAN DEFAULT false,
  created_at      TIMESTAMPTZ DEFAULT now(),
  updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 7. Job searches
CREATE TABLE IF NOT EXISTS public.job_searches (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     UUID REFERENCES public.users(id) ON DELETE SET NULL,
  run_id      TEXT,
  location    TEXT,
  role        TEXT,
  filters     JSONB,
  results     JSONB,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- 8. Job applications
CREATE TABLE IF NOT EXISTS public.job_applications (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID REFERENCES public.users(id) ON DELETE SET NULL,
  company_name        TEXT,
  job_title           TEXT,
  job_url             TEXT,
  application_status  TEXT DEFAULT 'saved',
  tailored_resume_id  UUID,
  outreach_email_id   TEXT,
  applied_at          TIMESTAMPTZ,
  updated_at          TIMESTAMPTZ DEFAULT now()
);

-- 9. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_readiness_audits_user ON public.readiness_audits(user_id);
CREATE INDEX IF NOT EXISTS idx_readiness_audits_role ON public.readiness_audits(target_role);
CREATE INDEX IF NOT EXISTS idx_one_thing_actions_audit ON public.one_thing_actions(audit_id);
CREATE INDEX IF NOT EXISTS idx_application_outcomes_user ON public.application_outcomes(user_id);
CREATE INDEX IF NOT EXISTS idx_application_outcomes_audit ON public.application_outcomes(audit_id);
CREATE INDEX IF NOT EXISTS idx_job_searches_run_id ON public.job_searches(run_id);
CREATE INDEX IF NOT EXISTS idx_resumes_token ON public.resumes(resume_token);

-- 10. Row Level Security (enable but keep permissive for now)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.readiness_audits ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.one_thing_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_applications ENABLE ROW LEVEL SECURITY;

-- Permissive policies (service_role bypasses RLS; anon/authenticated get full access for now)
CREATE POLICY "Allow all for authenticated" ON public.users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON public.resumes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON public.readiness_audits FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON public.one_thing_actions FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON public.application_outcomes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON public.learning_paths FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON public.job_searches FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for authenticated" ON public.job_applications FOR ALL USING (true) WITH CHECK (true);
