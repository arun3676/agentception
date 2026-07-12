from __future__ import annotations
import asyncio, os, math, random, re, httpx
from typing import List, Dict, Tuple

def _get_voyage_key():
    """Get Voyage API key, loading .env if needed"""
    key = os.getenv("VOYAGE_API_KEY")
    if not key:
        try:
            from dotenv import load_dotenv
            load_dotenv()
            key = os.getenv("VOYAGE_API_KEY")
        except ImportError:
            pass
    return key

EMBED_MODEL = os.getenv("EMBED_MODEL","voyage-3-large")
MATRYOSHKA_DIM = int(os.getenv("EMBED_DIM","256"))  # smaller dims save cost

# Voyage rate-limits per minute. Firing one embed call per job (10 concurrent on a
# normal search) reliably tripped 429s, and the caller's `except: return 0.0`
# turned that into "no semantic signal" — silently degrading the hybrid matcher to
# keyword-only. Serialise and retry instead of losing the signal.
EMBED_MAX_CONCURRENCY = int(os.getenv("EMBED_MAX_CONCURRENCY", "1"))
_EMBED_SEM = asyncio.Semaphore(max(1, EMBED_MAX_CONCURRENCY))
EMBED_MAX_RETRIES = int(os.getenv("EMBED_MAX_RETRIES", "5"))
# Voyage bills and rate-limits on tokens, so it's tempting to truncate hard. Don't:
# measured on the golden set, cutting JDs to 2.5k chars dropped match AUROC from
# 0.83 to 0.60. An ATS posting opens with company mission and benefits — the
# requirements that carry the hiring signal sit further down. See docs/EVALS.md.
EMBED_MAX_CHARS = int(os.getenv("EMBED_MAX_CHARS", "12000"))

def _norm(v):
    s = math.sqrt(sum(x*x for x in v)) or 1.0
    return [x/s for x in v]

async def _embed(texts: List[str]) -> List[List[float]]:
    """Embed a batch of texts. Pass every text you need in ONE call — Voyage bills
    and rate-limits per request, not per text."""
    if not texts: return []
    voyage_key = _get_voyage_key()
    if not voyage_key:
        raise ValueError("VOYAGE_API_KEY not set")

    payload = {
        "model": EMBED_MODEL,
        "input": [t[:EMBED_MAX_CHARS] for t in texts],
        "input_type": "document",
    }
    headers = {"Authorization": f"Bearer {voyage_key}", "Content-Type": "application/json"}

    last_error: Exception | None = None
    async with _EMBED_SEM:
        for attempt in range(EMBED_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=40) as client:
                    r = await client.post(
                        "https://api.voyageai.com/v1/embeddings", headers=headers, json=payload
                    )
                    r.raise_for_status()
                    data = r.json()["data"]
                return [_norm(d["embedding"]) for d in data]
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code not in (429, 500, 502, 503, 529):
                    raise
                # Voyage's limiter works on a per-minute window, so a 1-2s retry is
                # pointless — back off into the next window.
                delay = min(60.0, 5.0 * (2 ** attempt)) + random.uniform(0, 1.0)
                print(f"⚠️ Voyage {e.response.status_code}, retry in {delay:.0f}s "
                      f"({attempt + 1}/{EMBED_MAX_RETRIES})")
                await asyncio.sleep(delay)
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                await asyncio.sleep(1.0 * (2 ** attempt))

    raise RuntimeError(f"Voyage embedding failed after {EMBED_MAX_RETRIES} attempts: {last_error}")

def _cos(a: List[float], b: List[float]) -> float:
    return sum(x*y for x,y in zip(a,b))

def _extract_snippet(text: str, max_chars=800) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    return t[:max_chars]

async def match_role_to_pages(role_blob: str, pages: List[Dict[str,str]], role_keywords: List[str]) -> List[Dict]:
    """pages: [{url, text, title}]"""
    ref_vec = (await _embed([role_blob]))[0]
    snippets = [_extract_snippet(p.get("text","")) for p in pages]
    vecs = await _embed(snippets)
    out = []
    for p, v in zip(pages, vecs):
        sim = max(0.0, _cos(ref_vec, v))  # 0..1
        text_low = (p.get("text","")[:1200]).lower()
        matched_kw = sorted({kw for kw in role_keywords if kw.lower() in text_low})
        bonus = min(0.2, 0.04 * len(matched_kw))   # up to +0.2
        score = (sim + bonus) * 100.0
        why = []
        if matched_kw: why.append("mentions: " + ", ".join(matched_kw[:4]))
        if sim>0.5: why.append("content aligns with role")
        out.append({"url": p.get("url"), "match_score": round(score,1), "matched_keywords": matched_kw, "why": " · ".join(why)})
    # stable sort
    out.sort(key=lambda x: (-x["match_score"], x["url"] or ""))
    return out
