-- Migration: create application_outcomes table
-- Project: hikfndkbqdwxfxesfgdb
-- Run this in the Supabase SQL Editor:
-- https://supabase.com/dashboard/project/hikfndkbqdwxfxesfgdb/sql/new

CREATE TABLE IF NOT EXISTS application_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    audit_id UUID,
    company TEXT NOT NULL,
    role TEXT NOT NULL,
    outcome TEXT NOT NULL,
    outcome_logged_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_application_outcomes_user_id
    ON application_outcomes(user_id);

CREATE INDEX IF NOT EXISTS idx_application_outcomes_outcome_logged_at
    ON application_outcomes(outcome_logged_at DESC);
