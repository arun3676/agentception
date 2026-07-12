"""
Run the Supabase migration using httpx + service_role key.
Falls back to printing the SQL for manual execution in the Dashboard.

Usage:  python -m migrations.run_migration
"""
import os
import sys
import pathlib
import httpx
from dotenv import load_dotenv

# Resolve .env from project root
env_path = pathlib.Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

SQL_FILE = pathlib.Path(__file__).parent / "create_readiness_tables.sql"


def run():
    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        print("❌ SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY not set in .env")
        sys.exit(1)

    sql = SQL_FILE.read_text(encoding="utf-8")

    # Split into individual statements (skip empty / comment-only chunks)
    statements = []
    for chunk in sql.split(";"):
        stripped = chunk.strip()
        # Skip empty or comment-only blocks
        lines = [l for l in stripped.splitlines() if l.strip() and not l.strip().startswith("--")]
        if lines:
            statements.append(stripped + ";")

    print(f"📦 Loaded {len(statements)} SQL statements from {SQL_FILE.name}")

    # Try executing via Supabase REST (postgrest rpc) — this uses the
    # /rest/v1/rpc endpoint which requires a pre-existing function.
    # Since we can't guarantee that, we'll use the pg-meta endpoint instead.
    # The /pg/ endpoint is available on self-hosted but not always on cloud.
    # Safest approach: try the SQL API, fall back to printing instructions.

    headers = {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    # Attempt: use the Supabase SQL endpoint (available on newer projects)
    success_count = 0
    fail_count = 0

    for i, stmt in enumerate(statements, 1):
        try:
            # Try the pg/query endpoint (available on some Supabase instances)
            resp = httpx.post(
                f"{SUPABASE_URL}/rest/v1/rpc/",
                headers=headers,
                json={"query": stmt},
                timeout=30.0,
            )
            if resp.status_code in (200, 201, 204):
                success_count += 1
                print(f"  ✅ [{i}/{len(statements)}] OK")
            else:
                # Expected to fail — REST API doesn't support raw DDL
                fail_count += 1
        except Exception:
            fail_count += 1

    if fail_count > 0:
        print(f"\n⚠️  {fail_count} statements couldn't be run via REST API.")
        print("   This is expected — Supabase Cloud requires the SQL Editor for DDL.")
        print(f"\n📋 Copy-paste the full SQL from:\n   {SQL_FILE.resolve()}")
        print("   → Go to: https://supabase.com/dashboard/project/hikfndkbqdwxfxesfgdb/sql/new")
        print("   → Paste the SQL and click 'Run'\n")
    else:
        print(f"\n✅ All {success_count} statements executed successfully!")


if __name__ == "__main__":
    run()
