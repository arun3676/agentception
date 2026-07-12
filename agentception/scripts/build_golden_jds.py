"""Fetch real job descriptions into the eval golden set.

Evals must be reproducible and offline, so we snapshot the JD text to disk once.
Re-running only adds postings that aren't already captured.

    python scripts/build_golden_jds.py --per-role 6

Output: evals/golden/jds/<id>.txt  +  evals/golden/jds/index.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from server.agents.job_search import search_ats_with_exa  # noqa: E402
from server.tools.job_description_fetcher import fetch_job_description  # noqa: E402

OUT_DIR = ROOT / "evals" / "golden" / "jds"
INDEX = OUT_DIR / "index.jsonl"

# Spread across roles AND cities. Two reasons: skill extraction has to work for
# every career track the product supports, and the match eval needs enough
# in-domain / out-of-domain postings for AUROC to be more than noise (at n=14 a
# random scorer clears the gate a quarter of the time).
ROLES = [
    ("AI Engineer", "San Francisco, CA"),
    ("Machine Learning Engineer", "New York, NY"),
    ("LLM Engineer", "Remote"),
    ("Data Engineer", "New York, NY"),
    ("Data Engineer", "Chicago, IL"),
    ("Backend Engineer", "Austin, TX"),
    ("Backend Engineer", "Boston, MA"),
    ("DevOps Engineer", "Seattle, WA"),
    ("Site Reliability Engineer", "Denver, CO"),
    ("Frontend Engineer", "Remote"),
    ("Frontend Engineer", "Los Angeles, CA"),
    ("Mobile Engineer", "Remote"),
]

MIN_CHARS = 800  # anything shorter isn't a real JD


def jd_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()[:12]


def load_index() -> dict[str, dict]:
    if not INDEX.exists():
        return {}
    out = {}
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["id"]] = rec
    return out


async def collect(per_role: int) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = load_index()
    print(f"{len(index)} JDs already captured")

    for role, city in ROLES:
        print(f"\n=== {role} — {city}")
        try:
            hits = await search_ats_with_exa(role, city, num_results=per_role * 3)
        except Exception as e:
            print(f"  search failed: {e}")
            continue

        kept = 0
        for hit in hits:
            if kept >= per_role:
                break
            hid = jd_id(hit.url)
            if hid in index:
                continue

            try:
                text = await asyncio.wait_for(
                    fetch_job_description(hit.url, snippet=hit.snippet), timeout=30
                )
            except Exception as e:
                print(f"  fetch failed {hit.url[:60]}: {str(e)[:50]}")
                continue

            text = (text or "").strip()
            if len(text) < MIN_CHARS:
                print(f"  too short ({len(text)}c) {hit.url[:60]}")
                continue

            (OUT_DIR / f"{hid}.txt").write_text(text, encoding="utf-8")
            rec = {
                "id": hid,
                "url": hit.url,
                "title": re.sub(r"\s+", " ", hit.title or "").strip()[:120],
                "searched_role": role,
                "city": city,
                "chars": len(text),
            }
            index[hid] = rec
            kept += 1
            print(f"  + {hid} ({len(text)}c) {rec['title'][:55]}")

    with INDEX.open("w", encoding="utf-8") as f:
        for rec in index.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nTotal captured: {len(index)} JDs -> {OUT_DIR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-role", type=int, default=6)
    args = ap.parse_args()
    asyncio.run(collect(args.per_role))
