"""
Create the application_outcomes table in Supabase.
Project: hikfndkbqdwxfxesfgdb (confirmed)
"""
import os
import sys
from pathlib import Path

# This script lives in scripts/; the project root is one level up
_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv(_ROOT / ".env")

PROJECT_REF = "hikfndkbqdwxfxesfgdb"
SQL_EDITOR_URL = f"https://supabase.com/dashboard/project/{PROJECT_REF}/sql/new"

SQL = """
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
"""

def run_via_psycopg2():
    import psycopg2
    password = os.getenv("SUPABASE_DB_PASSWORD", "")
    if not password:
        return None, "SUPABASE_DB_PASSWORD not set in .env"

    conn_kwargs_list = [
        # Direct connection with IPv4 forced
        {"host": "db.hikfndkbqdwxfxesfgdb.supabase.co", "port": 5432, "dbname": "postgres",
         "user": "postgres", "password": password,
         "sslmode": "require", "connect_timeout": 15},
        # Pooler session mode (port 5432) with IPv4 forced
        {"host": "aws-0-us-east-1.pooler.supabase.com", "port": 5432, "dbname": "postgres",
         "user": f"postgres.{PROJECT_REF}", "password": password,
         "sslmode": "require", "connect_timeout": 15},
        # Pooler transaction mode (port 6543) with IPv4 forced
        {"host": "aws-0-us-east-1.pooler.supabase.com", "port": 6543, "dbname": "postgres",
         "user": f"postgres.{PROJECT_REF}", "password": password,
         "sslmode": "require", "connect_timeout": 15},
    ]

    for kwargs in conn_kwargs_list:
        try:
            print(f"  Attempting {kwargs['user']}@{kwargs['host']}:{kwargs['port']}...")
            conn = psycopg2.connect(**kwargs)
            conn.autocommit = True
            print(f"  OK: Connected")
            return conn, None
        except Exception as e:
            print(f"  Failed: {str(e)[:120]}")
            continue
    return None, "All connection attempts failed"

def verify(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'application_outcomes'
        ORDER BY ordinal_position
    """)
    rows = cur.fetchall()
    if not rows:
        print("WARN: Table not found or has no columns")
        cur.close()
        return False

    print("  Table confirmed with columns:")
    for col, dtype in rows:
        print(f"    - {col} ({dtype})")

    cur.execute("""
        INSERT INTO application_outcomes (user_id, company, role, outcome)
        VALUES ('00000000-0000-0000-0000-000000000001', '__verify__', '__verify__', '__verify__')
    """)
    cur.execute("DELETE FROM application_outcomes WHERE company = '__verify__'")
    cur.close()
    print("  Insert/delete verified")
    return True

def main():
    print(f"Project: {PROJECT_REF}")
    print(f"Supabase URL: {os.getenv('SUPABASE_URL', 'not set')}")

    conn, err = run_via_psycopg2()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(SQL)
            cur.close()
            print("Migration SQL executed successfully")
            if verify(conn):
                print("SUCCESS: Migration created and verified")
            else:
                print("WARN: Migration ran but verification failed")
        except Exception as e:
            print(f"ERROR during migration: {e}")
        finally:
            conn.close()
    else:
        print(f"\nCould not auto-migrate: {err}")
        print(f"\nTo complete the migration, run this SQL in the Supabase SQL Editor:")
        print(f"  {SQL_EDITOR_URL}")
        print(f"\nOr add SUPABASE_DB_PASSWORD to .env (from Dashboard > Settings > Database)")
        print(f"\n{SQL}")

if __name__ == "__main__":
    main()
