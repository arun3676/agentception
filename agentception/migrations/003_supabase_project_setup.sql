-- ============================================================================
-- Agentception — full schema for a FRESH Supabase project
-- Paste into: Dashboard → SQL Editor → Run   (safe to re-run)
--
-- This supersedes create_readiness_tables.sql and 002_application_outcomes.sql:
--   * create_readiness_tables.sql could never run as written — `current_role`
--     is a reserved word in Postgres, so CREATE TABLE users failed. Quoted here.
--   * 002's application_outcomes is an older subset (and its NOT NULL user_id
--     would break inserts from verdict_loop.py, which can log anonymous rows).
--   * ui/supabase/migrations/001 is NOT applied: it defines a conflicting
--     public.resumes keyed to auth.users for edge functions that no longer
--     exist. If the tailoring functions are ever rebuilt, reconcile then.
--
-- What the server actually reads/writes today:
--   readiness_audits      (audit_engine.py, cohort_analytics.py, /health)
--   application_outcomes  (verdict_loop.py, cohort_analytics.py)
--   one_thing_actions     (decision_engine.py)
-- The rest are forward-looking and cheap to keep.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Users (app-level profile rows; not a replacement for auth.users)
CREATE TABLE IF NOT EXISTS public.users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT UNIQUE,
  display_name  TEXT,
  "current_role" TEXT,           -- reserved word in Postgres; must stay quoted
  target_role   TEXT,
  location_preference TEXT,
  skills_json   JSONB DEFAULT '[]'::jsonb,
  resume_token  TEXT,
  created_at    TIMESTAMPTZ DEFAULT now(),
  updated_at    TIMESTAMPTZ DEFAULT now()
);

-- 2. Resumes
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

-- 3. Readiness audits — one row per audit run
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

-- 4. One-thing actions — the single next action generated from an audit
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
--    user_id is nullable ON PURPOSE: verdict_loop.py logs anonymous outcomes.
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

-- 6. Learning paths
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

-- 9. Indexes
CREATE INDEX IF NOT EXISTS idx_readiness_audits_user     ON public.readiness_audits(user_id);
CREATE INDEX IF NOT EXISTS idx_readiness_audits_role     ON public.readiness_audits(target_role);
CREATE INDEX IF NOT EXISTS idx_one_thing_actions_audit   ON public.one_thing_actions(audit_id);
CREATE INDEX IF NOT EXISTS idx_application_outcomes_user ON public.application_outcomes(user_id);
CREATE INDEX IF NOT EXISTS idx_application_outcomes_audit ON public.application_outcomes(audit_id);
CREATE INDEX IF NOT EXISTS idx_job_searches_run_id       ON public.job_searches(run_id);
CREATE INDEX IF NOT EXISTS idx_resumes_token             ON public.resumes(resume_token);

-- 10. Row Level Security.
-- The backend talks to these tables with the secret (service) key, which
-- bypasses RLS. Enabling RLS with NO policies means the anon/publishable key
-- can read NOTHING — which is correct: nothing in the browser queries these
-- tables directly. (The old permissive USING (true) policies gave every
-- anonymous visitor full read/write over everyone's data.)
ALTER TABLE public.users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.resumes              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.readiness_audits     ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.one_thing_actions    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.application_outcomes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.learning_paths       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_searches         ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_applications     ENABLE ROW LEVEL SECURITY;

-- Drop the old permissive policies if this is ever run over an old database.
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY['users','resumes','readiness_audits','one_thing_actions',
                           'application_outcomes','learning_paths','job_searches','job_applications']
  LOOP
    EXECUTE format('DROP POLICY IF EXISTS "Allow all for authenticated" ON public.%I', t);
  END LOOP;
END $$;

SELECT 'agentception schema ready' AS status;
