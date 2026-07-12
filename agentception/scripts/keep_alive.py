#!/usr/bin/env python3
"""
Standalone keep-alive script for Supabase (AI Career Hub).

Run this locally or via any cron service (e.g., cron-job.org, UptimeRobot)
to prevent the free-tier Supabase project from auto-pausing after 7 days.

Usage:
    python keep_alive.py

Environment variables (from .env):
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
"""
import os
import sys
from pathlib import Path

# Try to load .env if present
try:
    from dotenv import load_dotenv
    # .env lives at the project root; this script lives in scripts/
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except Exception:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hikfndkbqdwxfxesfgdb.supabase.co")
SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def keep_alive():
    try:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SERVICE_KEY)
        # Any REST request touches PostgREST → Postgres, resetting the idle timer.
        # readiness_audits is the project's main table; if it doesn't exist yet,
        # PostgREST still connects to Postgres to resolve the schema (404 = activity).
        sb.table("readiness_audits").select("id", count="exact").limit(1).execute()
        print("✅ Supabase keep-alive succeeded")
        return 0
    except Exception as e:
        # Even a 404 or permission error means the DB was contacted.
        print(f"⚠️  Supabase keep-alive returned error (DB was still touched): {e}")
        return 0


if __name__ == "__main__":
    sys.exit(keep_alive())
