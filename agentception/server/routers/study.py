from __future__ import annotations

"""Study-material search.

Turns any skill or job topic into a curated study view: hand-picked "verified
picks" (zero API cost, always present) plus live Exa results grouped into
videos / articles / courses / docs. Results are cached for a week because
learning material, unlike job postings, does not go stale quickly.
"""

import asyncio
import json
import pathlib
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, parse_qs, quote_plus

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..tools.exa_search import exa_search
from .cache import cached_search

router = APIRouter(prefix="/api/v1/study")

_DATA_DIR = pathlib.Path(__file__).parent.parent / "data" / "study"
_CACHE_TTL_SECONDS = 7 * 24 * 3600
_LEVELS = ("beginner", "intermediate", "advanced")


def _load(name: str) -> Any:
    with open(_DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


_PILLARS_FILE = _load("pillars.json")
_PILLARS: List[Dict[str, Any]] = _PILLARS_FILE["pillars"]
_COURSE_DOMAINS: List[str] = _PILLARS_FILE["course_domains"]
_DOCS_DOMAINS: List[str] = _PILLARS_FILE["docs_domains"]
_ROLE_RESOURCES: Dict[str, Any] = _load("role_resources.json")
_GOLD: List[Dict[str, Any]] = _load("gold_resources.json")

_GOLD_BY_CATEGORY = {g["category"]: g["domains"] for g in _GOLD}


class StudySearchBody(BaseModel):
    topic: str = Field(min_length=2, max_length=120)
    role: Optional[str] = Field(default=None, max_length=80)
    level: str = Field(default="intermediate")


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def resolve_pillar(topic: str, role: Optional[str]) -> Dict[str, Any]:
    """Pick the career pillar a topic belongs to. An explicit role wins; otherwise
    score pillars by how many of their keywords appear in the topic."""
    if role:
        role_key = _normalise(role)
        for pillar in _PILLARS:
            if pillar["key"] == role_key:
                return pillar
        role_l = role.lower()
        for pillar in _PILLARS:
            if pillar["label"].lower() in role_l or any(k in role_l for k in pillar["keywords"]):
                return pillar

    topic_l = topic.lower()
    best, best_score = None, 0
    for pillar in _PILLARS:
        score = sum(1 for kw in pillar["keywords"] if kw in topic_l)
        if score > best_score:
            best, best_score = pillar, score

    # Default to AI Engineer: it is the app's primary audience
    return best or _PILLARS[0]


def _level_data(pillar_key: str, level: str) -> Dict[str, Any]:
    level = level if level in _LEVELS else "intermediate"
    return (_ROLE_RESOURCES.get(pillar_key) or {}).get(level) or {}


def _trusted_domains(pillar: Dict[str, Any], level_data: Dict[str, Any]) -> List[str]:
    domains: List[str] = []
    for category in pillar.get("gold_categories", []):
        domains.extend(_GOLD_BY_CATEGORY.get(category, []))
    domains.extend(level_data.get("reading", []))
    domains.extend(level_data.get("courses", []))

    cleaned, seen = [], set()
    for d in domains:
        d = d.strip().lower().removeprefix("https://").removeprefix("http://").removeprefix("www.")
        if d and "." in d and d not in seen:
            seen.add(d)
            cleaned.append(d)
    # Exa caps includeDomains; keep the list focused
    return cleaned[:25]


def youtube_video_id(url: str) -> Optional[str]:
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    host = parsed.netloc.lower().removeprefix("www.")
    if host == "youtu.be":
        vid = parsed.path.lstrip("/")
        return vid or None
    if "youtube.com" in host:
        if parsed.path == "/watch":
            vid = parse_qs(parsed.query).get("v", [None])[0]
            return vid
        for prefix in ("/embed/", "/shorts/", "/live/"):
            if parsed.path.startswith(prefix):
                return parsed.path[len(prefix):].split("/")[0] or None
    return None


def _classify(url: str) -> str:
    host = ""
    try:
        host = urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        pass
    if any(host == d or host.endswith("." + d) for d in _COURSE_DOMAINS):
        return "courses"
    if host.startswith("docs.") or any(host == d or host.endswith("." + d) for d in _DOCS_DOMAINS):
        return "docs"
    return "articles"


def _to_item(res: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """None for results with no title or url — they render as dead 'Untitled' rows."""
    url = res.get("url") or ""
    title = (res.get("title") or "").strip()
    if not url or not title:
        return None

    highlights = res.get("highlights") or []
    snippet = " ".join(highlights) if highlights else (res.get("summary") or res.get("text") or "")
    return {
        "title": title,
        "url": url,
        "snippet": snippet.strip()[:400],
        "published": res.get("date") or "",
    }


# (source field in role_resources.json, pick kind, how to build its URL)
_CURATED_SOURCES = (
    ("youtube", "youtube_channel", lambda name: f"https://www.youtube.com/results?search_query={quote_plus(name)}"),
    ("reading", "site", lambda name: f"https://{name}"),
    ("courses", "course", lambda name: f"https://{name}"),
)


def _curated_picks(pillar: Dict[str, Any], level_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Hand-picked channels and sites for this role+level. No API call, always shown."""
    return [
        {"title": name, "kind": kind, "url": build_url(name)}
        for field, kind, build_url in _CURATED_SOURCES
        for name in level_data.get(field, [])
    ]


async def _search_videos(topic: str, level_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    channels = level_data.get("youtube", [])[:3]
    hint = f" from channels like {', '.join(channels)}" if channels else ""
    query = f"{topic} tutorial{hint}"
    try:
        results = await exa_search(
            query,
            include_domains=["youtube.com"],
            num_results=8,
            want_highlights=True,
        )
    except Exception as e:
        print(f"[Study] YouTube search failed: {e}")
        return []

    videos = []
    for res in results:
        item = _to_item(res)
        if not item:
            continue
        vid = youtube_video_id(item["url"])
        if not vid:
            continue  # channel/playlist pages, not watchable lessons
        item["video_id"] = vid
        item["thumbnail"] = f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
        videos.append(item)
    return videos


async def _search_web(topic: str, level: str, level_data: Dict[str, Any], pillar: Dict[str, Any]) -> List[Dict[str, Any]]:
    terms = level_data.get("search_terms", [])
    modifier = terms[0] if terms else "guide"
    query = f"{topic} {modifier}"
    domains = _trusted_domains(pillar, level_data)
    try:
        return await exa_search(
            query,
            include_domains=domains or None,
            num_results=12,
            want_highlights=True,
        )
    except Exception as e:
        print(f"[Study] Web search failed: {e}")
        return []


_INTERVIEW_TTL_SECONDS = 3 * 24 * 3600


@router.get("/interview-prep")
async def interview_prep(
    role: str = Query(min_length=2, max_length=80),
    company: Optional[str] = Query(default=None, max_length=120),
):
    """What the interview loop actually looks like. Tavily is the right tool here:
    this content lives in blog posts and forum threads, and Tavily returns the
    cleaned page text rather than a link to scrape."""
    from ..tools.tavily_search import tavily_search

    subject = f"{company} {role}" if company else role

    async def fetch() -> Dict[str, Any]:
        query = (
            f"{company} {role} interview process experience questions"
            if company
            else f"{role} interview questions and process"
        )
        try:
            results = await tavily_search(query, num_results=6, search_depth="advanced")
        except Exception as e:
            print(f"[InterviewPrep] search failed: {e}")
            results = []

        return {
            "role": role,
            "company": company,
            "sources": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": (r.get("content") or "")[:400],
                }
                for r in results
                if r.get("url")
            ],
        }

    return await cached_search(
        engine="interview_prep",
        subject=subject,
        params={},
        ttl_seconds=_INTERVIEW_TTL_SECONDS,
        fetch=fetch,
        should_cache=lambda p: bool(p["sources"]),
    )


@router.get("/pillars")
async def list_pillars():
    """The 12 career pillars, for the browseable Study page grid."""
    return {
        "pillars": [
            {"key": p["key"], "label": p["label"], "keywords": p["keywords"][:6]}
            for p in _PILLARS
        ]
    }


@router.post("/search")
async def search_study_materials(body: StudySearchBody):
    topic = body.topic.strip()
    if not topic:
        raise HTTPException(400, "topic is required")

    level = body.level if body.level in _LEVELS else "intermediate"
    pillar = resolve_pillar(topic, body.role)
    level_data = _level_data(pillar["key"], level)

    async def fetch() -> Dict[str, Any]:
        videos, web_results = await asyncio.gather(
            _search_videos(topic, level_data),
            _search_web(topic, level, level_data, pillar),
        )

        buckets: Dict[str, List[Dict[str, Any]]] = {"articles": [], "courses": [], "docs": []}
        for res in web_results:
            item = _to_item(res)
            if not item:
                continue
            buckets[_classify(item["url"])].append(item)

        return {
            "topic": topic,
            "level": level,
            "pillar": {"key": pillar["key"], "label": pillar["label"]},
            "videos": videos,
            "articles": buckets["articles"],
            "courses": buckets["courses"],
            "docs": buckets["docs"],
            "curated_picks": _curated_picks(pillar, level_data),
        }

    return await cached_search(
        engine="study",
        subject=topic,
        params={"level": level, "pillar": pillar["key"]},
        ttl_seconds=_CACHE_TTL_SECONDS,
        fetch=fetch,
        # Only cache runs that actually returned live material
        should_cache=lambda p: bool(p["videos"] or p["articles"] or p["courses"] or p["docs"]),
    )
