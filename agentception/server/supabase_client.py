"""
Supabase client singleton for the AI Career Hub project.
Uses the service_role key server-side for full DB access,
and exposes a lightweight client for backend CRUD.
"""
import os
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://hikfndkbqdwxfxesfgdb.supabase.co")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")


@lru_cache(maxsize=1)
def get_supabase_client():
    """Return a Supabase client using the service_role key (full access)."""
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except ImportError:
        print("⚠️  supabase-py not installed. Run: pip install supabase")
        return None
    except Exception as e:
        print(f"⚠️  Supabase client init failed: {e}")
        return None


@lru_cache(maxsize=1)
def get_supabase_anon():
    """Return a Supabase client using the anon key (RLS-restricted)."""
    try:
        from supabase import create_client
        return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
    except ImportError:
        return None
    except Exception as e:
        print(f"⚠️  Supabase anon client init failed: {e}")
        return None


# Quick alias
supabase = get_supabase_client
