from __future__ import annotations
import os, sqlite3, datetime as dt, json, hashlib
from typing import Iterable, Any, Optional, Tuple
from ..schemas import HousingLead, EventItem, PlaceItem
import datetime as dt
from typing import Set

# Tests must not write to the database the app is using. Point AGENTCEPTION_DB at a
# temp file in the test session and the whole store follows.
DB_PATH = os.path.abspath(
    os.getenv("AGENTCEPTION_DB")
    or os.path.join(os.path.dirname(__file__), "..", "..", "data", "agentception.db")
)

def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS housing (
            id INTEGER PRIMARY KEY,
            ts TEXT, title TEXT, price INT, url TEXT UNIQUE, neighborhood TEXT, distance_km REAL, notes TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            ts TEXT, title TEXT, date TEXT, url TEXT UNIQUE, area TEXT, distance_km REAL, why_attend TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS places (
            id INTEGER PRIMARY KEY,
            ts TEXT, name TEXT, category TEXT, rating REAL,
            url TEXT UNIQUE, lat REAL, lng REAL, source TEXT
        )""")
        # URL memory and preferences
        c.execute("""CREATE TABLE IF NOT EXISTS listings_seen (
            url TEXT PRIMARY KEY,
            domain TEXT,
            status TEXT,
            reason TEXT,
            first_seen TEXT,
            last_seen TEXT,
            visits INTEGER DEFAULT 1
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS user_prefs (
            k TEXT PRIMARY KEY,
            v TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS pins (
            url TEXT PRIMARY KEY,
            title TEXT,
            ts TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS saved (
            id INTEGER PRIMARY KEY,
            ts TEXT, kind TEXT, url TEXT UNIQUE, title TEXT, data TEXT
        )""")
        # Search cache for web_search results (engine-specific)
        c.execute("""CREATE TABLE IF NOT EXISTS search_cache (
            key TEXT PRIMARY KEY,
            engine TEXT,
            query TEXT,
            params_hash TEXT,
            ts TEXT,
            expires_at TEXT,
            results_json TEXT
        )""")
        # API usage tracking for budget guards
        c.execute("""CREATE TABLE IF NOT EXISTS api_usage (
            provider TEXT,
            ts TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS ai_resources (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            url TEXT NOT NULL,
            category TEXT,
            tags_json TEXT,
            difficulty TEXT,
            cost TEXT,
            verified INT DEFAULT 1,
            upvotes INT DEFAULT 0,
            added_at TEXT,
            updated_at TEXT,
            featured INT DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS resource_bookmarks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            notes TEXT,
            completed INT DEFAULT 0,
            bookmarked_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS learning_paths (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            title TEXT,
            topic TEXT,
            expertise_level TEXT,
            path_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS job_applications (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            company_name TEXT,
            job_title TEXT,
            job_url TEXT,
            application_status TEXT,
            created_at TEXT,
            updated_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS progress_tracking (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            learning_path_id TEXT,
            milestone_identifier TEXT,
            resource_url TEXT,
            completion_status TEXT,
            completed_at TEXT,
            notes TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS readiness_audits (
            id TEXT PRIMARY KEY,
            run_id TEXT,
            user_id TEXT,
            target_role TEXT,
            resume_token TEXT,
            jd_count INTEGER DEFAULT 0,
            verdict_text TEXT,
            gap_type TEXT,
            gap_details TEXT,
            strengths TEXT,
            percentile INTEGER,
            raw_audit TEXT,
            status TEXT DEFAULT 'in_progress',
            created_at TEXT,
            updated_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS application_outcomes (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            audit_id TEXT,
            company TEXT,
            role TEXT,
            outcome TEXT,
            outcome_logged_at TEXT
        )""")

        # Search runs. These used to live only in an in-process dict, so a restart
        # (or a second instance) lost every result the user had just paid for in
        # API calls. Now the run survives the process that created it.
        c.execute("""CREATE TABLE IF NOT EXISTS search_runs (
            run_id TEXT PRIMARY KEY,
            user_id TEXT,
            role TEXT,
            city TEXT,
            doc_json TEXT,
            created_at TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_search_runs_user ON search_runs(user_id, created_at)")

        # Every paid model call, so cost is attributable rather than a monthly surprise.
        c.execute("""CREATE TABLE IF NOT EXISTS llm_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            provider TEXT,
            model TEXT,
            purpose TEXT,
            tokens_in INTEGER,
            tokens_out INTEGER,
            cost_usd REAL,
            latency_ms INTEGER,
            ok INTEGER,
            error TEXT
        )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_llm_calls_ts ON llm_calls(ts)")
        c.commit()


# --------- Search run persistence ---------

def search_run_save(run_id: str, user_id: Optional[str], role: str, city: str, doc: dict) -> None:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            c.execute(
                "REPLACE INTO search_runs (run_id, user_id, role, city, doc_json, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (run_id, user_id, role, city, json.dumps(doc, ensure_ascii=False, default=str), now),
            )
            c.commit()
        except Exception as e:
            print(f"⚠️ failed to persist run {run_id}: {e}")


def search_run_get(run_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT doc_json FROM search_runs WHERE run_id=?", (run_id,)).fetchone()
    if not row:
        return None
    try:
        return json.loads(row[0])
    except (json.JSONDecodeError, TypeError):
        return None


def search_runs_for_user(user_id: str, limit: int = 20) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT run_id, role, city, created_at FROM search_runs "
            "WHERE user_id=? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [{"run_id": r[0], "role": r[1], "city": r[2], "created_at": r[3]} for r in rows or []]


# --------- LLM cost tracking ---------

def llm_call_record(
    provider: str, model: str, purpose: str, tokens_in: int, tokens_out: int,
    cost_usd: float, latency_ms: int, ok: bool, error: Optional[str] = None,
) -> None:
    with _conn() as c:
        try:
            c.execute(
                "INSERT INTO llm_calls (ts, provider, model, purpose, tokens_in, tokens_out, "
                "cost_usd, latency_ms, ok, error) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (dt.datetime.utcnow().isoformat(), provider, model, purpose, tokens_in,
                 tokens_out, cost_usd, latency_ms, 1 if ok else 0, error),
            )
            c.commit()
        except Exception:
            pass  # telemetry must never break the request it is measuring


def llm_usage_summary(days: int = 7) -> dict:
    since = (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat()
    with _conn() as c:
        totals = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(cost_usd),0), COALESCE(SUM(tokens_in),0), "
            "COALESCE(SUM(tokens_out),0), COALESCE(AVG(latency_ms),0), "
            "COALESCE(SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END),0) "
            "FROM llm_calls WHERE ts >= ?", (since,)
        ).fetchone()
        by_provider = c.execute(
            "SELECT provider, model, COUNT(*), COALESCE(SUM(cost_usd),0) FROM llm_calls "
            "WHERE ts >= ? GROUP BY provider, model ORDER BY SUM(cost_usd) DESC", (since,)
        ).fetchall()
        by_purpose = c.execute(
            "SELECT purpose, COUNT(*), COALESCE(SUM(cost_usd),0) FROM llm_calls "
            "WHERE ts >= ? GROUP BY purpose ORDER BY SUM(cost_usd) DESC", (since,)
        ).fetchall()

    return {
        "window_days": days,
        "calls": totals[0],
        "cost_usd": round(totals[1], 4),
        "tokens_in": totals[2],
        "tokens_out": totals[3],
        "avg_latency_ms": round(totals[4]),
        "failures": totals[5],
        "by_model": [
            {"provider": r[0], "model": r[1], "calls": r[2], "cost_usd": round(r[3], 4)}
            for r in by_provider or []
        ],
        "by_purpose": [
            {"purpose": r[0], "calls": r[1], "cost_usd": round(r[2], 4)}
            for r in by_purpose or []
        ],
    }


def purge_user_data(user_id: str) -> dict[str, int]:
    """Hard-delete everything tied to a user. Backs the 'delete my data' endpoint —
    which has to actually delete things for the privacy claim to be true."""
    deleted: dict[str, int] = {}
    with _conn() as c:
        for table in ("search_runs", "job_applications", "learning_paths",
                      "application_outcomes", "resource_bookmarks"):
            try:
                cur = c.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
                deleted[table] = cur.rowcount
            except Exception:
                deleted[table] = 0
        c.commit()
    return deleted

def insert_housing(items: Iterable[HousingLead]):
    ts = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        for h in items:
            try:
                c.execute("INSERT OR IGNORE INTO housing (ts,title,price,url,neighborhood,distance_km,notes) VALUES (?,?,?,?,?,?,?)",
                          (ts,h.title,h.price,h.url,h.neighborhood,h.distance_km,h.notes))
            except Exception:
                pass
        c.commit()

def insert_events(items: Iterable[EventItem]):
    ts = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        for e in items:
            try:
                c.execute("INSERT OR IGNORE INTO events (ts,title,date,url,area,distance_km,why_attend) VALUES (?,?,?,?,?,?,?)",
                          (ts,e.title,e.date,e.url,e.area,e.distance_km,e.why_attend))
            except Exception:
                pass
        c.commit()

def insert_places(items: Iterable["PlaceItem"]):
    ts = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        for p in items:
            try:
                c.execute("INSERT OR IGNORE INTO places (ts,name,category,rating,url,lat,lng,source) VALUES (?,?,?,?,?,?,?,?)",
                          (ts,p.name,p.category,p.rating,p.url,p.lat,p.lng,p.source))
            except Exception:
                pass
        c.commit()

# --------- URL memory helpers ---------
def listings_get_status(url: str) -> Optional[str]:
    with _conn() as c:
        row = c.execute("SELECT status FROM listings_seen WHERE url=?", (url,)).fetchone()
        return row[0] if row else None

def listings_mark(url: str, domain: str, status: str, reason: Optional[str] = None) -> None:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            row = c.execute("SELECT visits FROM listings_seen WHERE url=?", (url,)).fetchone()
            if row:
                visits = int(row[0]) + 1
                c.execute("UPDATE listings_seen SET status=?, reason=?, last_seen=?, visits=? WHERE url=?",
                          (status, reason, now, visits, url))
            else:
                c.execute("INSERT INTO listings_seen (url,domain,status,reason,first_seen,last_seen,visits) VALUES (?,?,?,?,?,?,?)",
                          (url, domain, status, reason, now, now, 1))
            c.commit()
        except Exception:
            pass

# --------- Preferences ---------
def prefs_get(key: str, default: Optional[str] = None) -> Optional[str]:
    with _conn() as c:
        row = c.execute("SELECT v FROM user_prefs WHERE k=?", (key,)).fetchone()
        return row[0] if row else default

def prefs_set(key: str, value: str) -> None:
    with _conn() as c:
        try:
            c.execute("REPLACE INTO user_prefs (k,v) VALUES (?,?)", (key, value))
            c.commit()
        except Exception:
            pass

# --------- Pins ---------
def pins_add(url: str, title: str) -> None:
    with _conn() as c:
        try:
            c.execute("REPLACE INTO pins (url,title,ts) VALUES (?,?,?)", (url, title, dt.datetime.utcnow().isoformat()))
            c.commit()
        except Exception:
            pass

def pins_all() -> list[tuple[str, str]]:
    with _conn() as c:
        rows = c.execute("SELECT url,title FROM pins ORDER BY ts DESC").fetchall()
        return [(r[0], r[1]) for r in rows or []]

# --------- Search cache helpers ---------

def _serialize_params(params: dict) -> str:
    try:
        return json.dumps(params, sort_keys=True, separators=(",", ":"))
    except Exception:
        return "{}"

def compute_search_cache_key(engine: str, query: str, params: dict) -> str:
    payload = {
        "engine": engine,
        "query": query.strip().lower(),
        "params": params or {},
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()

def search_cache_get(key: str) -> Optional[Any]:
    now = dt.datetime.utcnow()
    with _conn() as c:
        row = c.execute("SELECT results_json, expires_at FROM search_cache WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        results_json, expires_at = row
        try:
            if expires_at:
                exp = dt.datetime.fromisoformat(expires_at)
                if exp < now:
                    # Expired - purge and return None
                    try:
                        c.execute("DELETE FROM search_cache WHERE key=?", (key,))
                        c.commit()
                    except Exception:
                        pass
                    return None
        except Exception:
            return None
        try:
            return json.loads(results_json)
        except Exception:
            return None

def search_cache_set(key: str, engine: str, query: str, params: dict, results: Any, ttl_seconds: int) -> None:
    now = dt.datetime.utcnow()
    expires_at = now + dt.timedelta(seconds=max(60, int(ttl_seconds)))
    with _conn() as c:
        try:
            c.execute(
                "REPLACE INTO search_cache (key, engine, query, params_hash, ts, expires_at, results_json) VALUES (?,?,?,?,?,?,?)",
                (
                    key,
                    engine,
                    query,
                    hashlib.sha1(_serialize_params(params).encode("utf-8")).hexdigest(),
                    now.isoformat(),
                    expires_at.isoformat(),
                    json.dumps(results, ensure_ascii=False),
                ),
            )
            c.commit()
        except Exception:
            pass

# --------- AI resource library ---------
def resources_count() -> int:
    with _conn() as c:
        row = c.execute("SELECT COUNT(*) FROM ai_resources").fetchone()
        return int(row[0]) if row else 0

def resources_upsert_many(resources: list[dict]) -> None:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        for r in resources:
            try:
                c.execute(
                    """REPLACE INTO ai_resources
                    (id, title, description, url, category, tags_json, difficulty, cost, verified, upvotes, added_at, updated_at, featured)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        r.get("id"),
                        r.get("title"),
                        r.get("description"),
                        r.get("url"),
                        r.get("category"),
                        json.dumps(r.get("tags", [])),
                        r.get("difficulty"),
                        r.get("cost"),
                        1 if r.get("verified", True) else 0,
                        int(r.get("upvotes", 0)),
                        r.get("added_at") or now,
                        r.get("updated_at") or now,
                        1 if r.get("featured", False) else 0,
                    ),
                )
            except Exception:
                pass
        c.commit()

def _row_to_resource(row: tuple) -> dict:
    return {
        "id": row[0],
        "title": row[1],
        "description": row[2],
        "url": row[3],
        "category": row[4],
        "tags": json.loads(row[5] or "[]"),
        "difficulty": row[6],
        "cost": row[7],
        "verified": bool(row[8]),
        "upvotes": int(row[9] or 0),
        "added_at": row[10],
        "updated_at": row[11],
        "featured": bool(row[12]),
    }

def resources_list(
    query: Optional[str] = None,
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    cost: Optional[str] = None,
    tag: Optional[str] = None,
    featured: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, title, description, url, category, tags_json, difficulty, cost, verified, upvotes, added_at, updated_at, featured "
            "FROM ai_resources"
        ).fetchall()
    resources = [_row_to_resource(r) for r in rows or []]
    if query:
        q = query.strip().lower()
        resources = [
            r for r in resources
            if q in (r.get("title") or "").lower() or q in (r.get("description") or "").lower()
        ]
    if category:
        resources = [r for r in resources if (r.get("category") or "").lower() == category.lower()]
    if difficulty:
        resources = [r for r in resources if (r.get("difficulty") or "").lower() == difficulty.lower()]
    if cost:
        resources = [r for r in resources if (r.get("cost") or "").lower() == cost.lower()]
    if tag:
        t = tag.strip().lower()
        resources = [r for r in resources if any(t == (x or "").lower() for x in r.get("tags", []))]
    if featured is True:
        resources = [r for r in resources if r.get("featured")]
    resources.sort(key=lambda r: (-int(r.get("featured", False)), -int(r.get("upvotes", 0))))
    return resources[offset:offset + max(1, int(limit))]

def resources_get(resource_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT id, title, description, url, category, tags_json, difficulty, cost, verified, upvotes, added_at, updated_at, featured "
            "FROM ai_resources WHERE id=?",
            (resource_id,),
        ).fetchone()
    return _row_to_resource(row) if row else None

def resources_categories() -> list[str]:
    with _conn() as c:
        rows = c.execute("SELECT DISTINCT category FROM ai_resources WHERE category IS NOT NULL").fetchall()
    return sorted({r[0] for r in rows if r and r[0]})

def resources_featured(limit: int = 20) -> list[dict]:
    return resources_list(featured=True, limit=limit, offset=0)

def resources_upvote(resource_id: str) -> Optional[dict]:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            c.execute("UPDATE ai_resources SET upvotes = upvotes + 1, updated_at=? WHERE id=?", (now, resource_id))
            c.commit()
        except Exception:
            pass
    return resources_get(resource_id)

def resource_bookmark_add(user_id: str, resource_id: str, notes: Optional[str] = None) -> Optional[dict]:
    now = dt.datetime.utcnow().isoformat()
    bookmark_id = hashlib.sha1(f"{user_id}:{resource_id}".encode("utf-8")).hexdigest()
    with _conn() as c:
        try:
            c.execute(
                "REPLACE INTO resource_bookmarks (id, user_id, resource_id, notes, completed, bookmarked_at) VALUES (?,?,?,?,?,?)",
                (bookmark_id, user_id, resource_id, notes or "", 0, now),
            )
            c.commit()
        except Exception:
            return None
    return {"id": bookmark_id, "user_id": user_id, "resource_id": resource_id, "notes": notes or "", "completed": False, "bookmarked_at": now}

def resource_bookmarks_list(user_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, user_id, resource_id, notes, completed, bookmarked_at FROM resource_bookmarks WHERE user_id=? ORDER BY bookmarked_at DESC",
            (user_id,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "resource_id": r[2],
            "notes": r[3],
            "completed": bool(r[4]),
            "bookmarked_at": r[5],
        }
        for r in rows or []
    ]

# --------- Learning paths (SQLite backing) ---------
def learning_path_save(path_id: str, user_id: Optional[str], title: str, topic: str, expertise_level: str, path_json: dict) -> None:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            c.execute(
                "REPLACE INTO learning_paths (id, user_id, title, topic, expertise_level, path_json, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (path_id, user_id, title, topic, expertise_level, json.dumps(path_json), now, now),
            )
            c.commit()
        except Exception:
            pass

def learning_path_get(path_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT id, user_id, title, topic, expertise_level, path_json, created_at, updated_at FROM learning_paths WHERE id=?",
            (path_id,),
        ).fetchone()
    if not row:
        return None
    try:
        return {
            "id": row[0],
            "user_id": row[1],
            "title": row[2],
            "topic": row[3],
            "expertise_level": row[4],
            "path": json.loads(row[5] or "{}"),
            "created_at": row[6],
            "updated_at": row[7],
        }
    except Exception:
        return None

def learning_path_list(user_id: Optional[str] = None, limit: int = 20) -> List[dict]:
    with _conn() as c:
        if user_id:
            rows = c.execute(
                "SELECT id, user_id, title, topic, expertise_level, path_json, created_at, updated_at FROM learning_paths WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, user_id, title, topic, expertise_level, path_json, created_at, updated_at FROM learning_paths ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    results: List[dict] = []
    for row in rows:
        try:
            results.append({
                "id": row[0],
                "user_id": row[1],
                "title": row[2],
                "topic": row[3],
                "expertise_level": row[4],
                "path": json.loads(row[5] or "{}"),
                "created_at": row[6],
                "updated_at": row[7],
            })
        except Exception:
            continue
    return results


def progress_upsert(
    progress_id: str,
    user_id: Optional[str],
    learning_path_id: Optional[str],
    milestone_identifier: str,
    resource_url: Optional[str],
    completion_status: str,
    notes: Optional[str] = None,
) -> None:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            c.execute(
                "REPLACE INTO progress_tracking (id, user_id, learning_path_id, milestone_identifier, resource_url, completion_status, completed_at, notes) VALUES (?,?,?,?,?,?,?,?)",
                (progress_id, user_id, learning_path_id, milestone_identifier, resource_url, completion_status, now, notes or ""),
            )
            c.commit()
        except Exception:
            pass

# --------- Application tracking ---------
def job_application_add(
    app_id: str,
    user_id: Optional[str],
    company_name: str,
    job_title: str,
    job_url: str,
    application_status: str,
) -> dict:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            c.execute(
                "REPLACE INTO job_applications (id, user_id, company_name, job_title, job_url, application_status, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
                (app_id, user_id, company_name, job_title, job_url, application_status, now, now),
            )
            c.commit()
        except Exception:
            pass
    return {
        "id": app_id,
        "user_id": user_id,
        "company_name": company_name,
        "job_title": job_title,
        "job_url": job_url,
        "application_status": application_status,
        "created_at": now,
        "updated_at": now,
    }

def job_applications_list(user_id: Optional[str] = None) -> list[dict]:
    with _conn() as c:
        if user_id:
            rows = c.execute(
                "SELECT id, user_id, company_name, job_title, job_url, application_status, created_at, updated_at FROM job_applications WHERE user_id=? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT id, user_id, company_name, job_title, job_url, application_status, created_at, updated_at FROM job_applications ORDER BY created_at DESC"
            ).fetchall()
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "company_name": r[2],
            "job_title": r[3],
            "job_url": r[4],
            "application_status": r[5],
            "created_at": r[6],
            "updated_at": r[7],
        }
        for r in rows or []
    ]

def job_application_update_status(app_id: str, status: str, user_id: Optional[str] = None) -> Optional[dict]:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            if user_id:
                cursor = c.execute(
                    "UPDATE job_applications SET application_status=?, updated_at=? WHERE id=? AND user_id=?",
                    (status, now, app_id, user_id),
                )
            else:
                cursor = c.execute(
                    "UPDATE job_applications SET application_status=?, updated_at=? WHERE id=?",
                    (status, now, app_id),
                )
            c.commit()
        except Exception:
            return None
    if cursor.rowcount == 0:
        return None
    # Fetch updated record
    rows = job_applications_list(user_id=user_id)
    for row in rows:
        if row["id"] == app_id:
            return row
    return None

# --------- Readiness audit persistence ---------

def audit_save(
    audit_id: str,
    run_id: str,
    user_id: str,
    target_role: str,
    resume_token: str = "",
    jd_count: int = 0,
    verdict_text: str = "",
    gap_type: str = "",
    gap_details: dict | None = None,
    strengths: list | None = None,
    percentile: int = 0,
    raw_audit: dict | None = None,
    status: str = "in_progress",
) -> None:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            existing = c.execute("SELECT id FROM readiness_audits WHERE id=?", (audit_id,)).fetchone()
            if existing:
                c.execute(
                    """UPDATE readiness_audits SET run_id=?, user_id=?, target_role=?, resume_token=?, jd_count=?,
                       verdict_text=?, gap_type=?, gap_details=?, strengths=?, percentile=?, raw_audit=?,
                       status=?, updated_at=? WHERE id=?""",
                    (run_id, user_id, target_role, resume_token, jd_count,
                     verdict_text, gap_type, json.dumps(gap_details or {}), json.dumps(strengths or []),
                     percentile, json.dumps(raw_audit or {}), status, now, audit_id),
                )
            else:
                c.execute(
                    """INSERT INTO readiness_audits (id, run_id, user_id, target_role, resume_token, jd_count,
                       verdict_text, gap_type, gap_details, strengths, percentile, raw_audit,
                       status, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (audit_id, run_id, user_id, target_role, resume_token, jd_count,
                     verdict_text, gap_type, json.dumps(gap_details or {}), json.dumps(strengths or []),
                     percentile, json.dumps(raw_audit or {}), status, now, now),
                )
            c.commit()
        except Exception:
            pass

def audit_get(audit_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT id, run_id, user_id, target_role, resume_token, jd_count, verdict_text, gap_type, "
            "gap_details, strengths, percentile, raw_audit, status, created_at, updated_at "
            "FROM readiness_audits WHERE id=?",
            (audit_id,),
        ).fetchone()
    if not row:
        return None
    try:
        return {
            "audit_id": row[0],
            "run_id": row[1],
            "user_id": row[2],
            "target_role": row[3],
            "resume_token": row[4],
            "jd_count": row[5],
            "verdict_text": row[6],
            "gap_type": row[7],
            "gap_details": json.loads(row[8] or "{}"),
            "strengths": json.loads(row[9] or "[]"),
            "percentile": row[10],
            "raw_audit": json.loads(row[11] or "{}"),
            "status": row[12],
            "created_at": row[13],
            "updated_at": row[14],
        }
    except Exception:
        return None

def audit_get_by_run_id(run_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM readiness_audits WHERE run_id=? ORDER BY updated_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    if not row:
        return None
    return audit_get(row[0])

def audit_update_status(audit_id: str, status: str) -> None:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            c.execute("UPDATE readiness_audits SET status=?, updated_at=? WHERE id=?", (status, now, audit_id))
            c.commit()
        except Exception:
            pass

def audit_get_for_user(user_id: str, limit: int = 10) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id FROM readiness_audits WHERE user_id=? ORDER BY updated_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    result = []
    for row in rows or []:
        audit = audit_get(row[0])
        if audit:
            result.append(audit)
    return result

# --------- Application outcomes persistence (durable fallback for Verdict Loop) ---------

def outcome_log(
    outcome_id: str,
    user_id: str,
    company: str,
    role: str,
    outcome: str,
    audit_id: str = "",
) -> dict:
    now = dt.datetime.utcnow().isoformat()
    with _conn() as c:
        try:
            c.execute(
                "REPLACE INTO application_outcomes (id, user_id, audit_id, company, role, outcome, outcome_logged_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (outcome_id, user_id, audit_id, company, role, outcome, now),
            )
            c.commit()
        except Exception:
            pass
    return {
        "ok": True,
        "id": outcome_id,
        "user_id": user_id,
        "company": company,
        "role": role,
        "outcome": outcome,
        "audit_id": audit_id,
        "outcome_logged_at": now,
        "storage": "sqlite",
    }

def outcomes_for_user(user_id: str, limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT id, user_id, audit_id, company, role, outcome, outcome_logged_at "
            "FROM application_outcomes WHERE user_id=? ORDER BY outcome_logged_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [
        {
            "id": r[0],
            "user_id": r[1],
            "audit_id": r[2],
            "company": r[3],
            "role": r[4],
            "outcome": r[5],
            "outcome_logged_at": r[6],
        }
        for r in rows or []
    ]

# --------- API usage helpers ---------

def api_usage_record(provider: str) -> None:
    with _conn() as c:
        try:
            c.execute("INSERT INTO api_usage (provider, ts) VALUES (?,?)", (provider, dt.datetime.utcnow().isoformat()))
            c.commit()
        except Exception:
            pass

def api_usage_calls_today(provider: str) -> int:
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) FROM api_usage WHERE provider=? AND DATE(ts)=DATE('now')",
            (provider,),
        ).fetchone()
        return int(row[0] if row and row[0] is not None else 0)

def api_usage_last_call_iso(provider: str) -> Optional[str]:
    with _conn() as c:
        row = c.execute(
            "SELECT ts FROM api_usage WHERE provider=? ORDER BY ts DESC LIMIT 1",
            (provider,),
        ).fetchone()
        return row[0] if row else None

# --------- Recently shown helpers ---------

def _since_days(days: int) -> str:
    return (dt.datetime.utcnow() - dt.timedelta(days=days)).isoformat()

def recent_seen_urls(kind: str, days: int) -> Set[str]:
    since = _since_days(days)
    table = "events" if kind == "event" else ("housing" if kind == "housing" else "places")
    with _conn() as c:
        cur = c.execute(f"SELECT url FROM {table} WHERE ts >= ?", (since,))
        return set(row[0] for row in cur.fetchall() if row and row[0])

def fetch_recent_housing(limit: int = 24, days: int = 7) -> list[HousingLead]:
    since = _since_days(days)
    with _conn() as c:
        rows = c.execute(
            "SELECT title, price, url, neighborhood, distance_km, notes FROM housing WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
            (since, limit),
        ).fetchall() or []
    out: list[HousingLead] = []
    for r in rows:
        try:
            out.append(HousingLead(title=r[0], price=int(r[1]), url=r[2], neighborhood=r[3], distance_km=float(r[4]), notes=r[5] or ""))
        except Exception:
            continue
    return out

def fetch_recent_events(limit: int = 12, days: int = 14) -> list[EventItem]:
    since = _since_days(days)
    with _conn() as c:
        rows = c.execute(
            "SELECT title, date, url, area, distance_km, why_attend FROM events WHERE ts >= ? ORDER BY ts DESC LIMIT ?",
            (since, limit),
        ).fetchall() or []
    out: list[EventItem] = []
    for r in rows:
        try:
            out.append(EventItem(title=r[0], date=r[1] or "", url=r[2], area=r[3], distance_km=float(r[4] or 0.0), why_attend=r[5] or ""))
        except Exception:
            continue
    return out

def save_add(kind: str, item: dict):
    ts = dt.datetime.utcnow().isoformat()
    url = item.get("url","")
    title = item.get("title") or item.get("name") or ""
    with _conn() as c:
        c.execute("INSERT OR IGNORE INTO saved (ts,kind,url,title,data) VALUES (?,?,?,?,?)",
                  (ts, kind, url, title, json.dumps(item)))
        c.commit()

def save_list(kind: str | None = None):
    q = "SELECT kind,url,title,data,ts FROM saved"
    args = ()
    if kind:
        q += " WHERE kind=?"
        args = (kind,)
    with _conn() as c:
        cur = c.execute(q, args)
        rows = cur.fetchall()
    out = []
    for k,u,t,d,ts in rows:
        try: obj = json.loads(d)
        except: obj = {"url": u, "title": t}
        obj.update({"kind": k, "ts": ts})
        out.append(obj)
    return out
