from __future__ import annotations
import os, sqlite3, datetime as dt, json, hashlib
from typing import Iterable, Any, Optional, Tuple
from ..schemas import HousingLead, EventItem, PlaceItem
import datetime as dt
from typing import Set

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "agentception.db"))

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
        c.commit()

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
