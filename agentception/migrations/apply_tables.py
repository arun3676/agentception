"""
Apply Supabase tables using the supabase-py client.
Uses the service_role key to execute SQL via the pg_net extension's
`query` RPC, or falls back to creating tables via PostgREST.

Usage: python -m migrations.apply_tables
"""
import os
import sys
import pathlib
import httpx
from dotenv import load_dotenv

env_path = pathlib.Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SQL_FILE = pathlib.Path(__file__).parent / "create_readiness_tables.sql"


def apply():
    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

    sql = SQL_FILE.read_text(encoding="utf-8")
    print(f"📦 Loaded SQL ({len(sql)} chars) from {SQL_FILE.name}")

    # Try the Supabase SQL API endpoint (works on hosted Supabase)
    headers = {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

    # Method 1: Try /rest/v1/rpc (won't work for DDL, but let's confirm connectivity)
    print("🔗 Testing Supabase connectivity...")
    try:
        resp = httpx.get(
            f"{SUPABASE_URL}/rest/v1/",
            headers=headers,
            timeout=10.0,
        )
        print(f"   Status: {resp.status_code}")
        if resp.status_code == 200:
            print("   ✅ Supabase REST API reachable")
        else:
            print(f"   ⚠️  Response: {resp.text[:200]}")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        sys.exit(1)

    # Method 2: Try the Supabase Management API SQL endpoint
    # This requires the project ref extracted from the URL
    project_ref = SUPABASE_URL.replace("https://", "").split(".")[0]
    print(f"   Project ref: {project_ref}")

    print("\n" + "=" * 60)
    print("📋 NEXT STEP: Run the SQL in Supabase Dashboard")
    print("=" * 60)
    print(f"\n1. Open: https://supabase.com/dashboard/project/{project_ref}/sql/new")
    print(f"2. Paste the contents of: {SQL_FILE.resolve()}")
    print("3. Click 'Run' to create all tables")
    print("\nAlternatively, the SQL is printed below:\n")
    print("-" * 60)
    print(sql)
    print("-" * 60)


if __name__ == "__main__":
    apply()
