from __future__ import annotations
import os, math, re, httpx
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

def _norm(v): 
    s = math.sqrt(sum(x*x for x in v)) or 1.0
    return [x/s for x in v]

async def _embed(texts: List[str]) -> List[List[float]]:
    if not texts: return []
    voyage_key = _get_voyage_key()
    if not voyage_key:
        raise ValueError("VOYAGE_API_KEY not set")
    headers = {"Authorization": f"Bearer {voyage_key}", "Content-Type": "application/json"}
    payload = {"model": EMBED_MODEL, "input": texts, "input_type":"document"}
    async with httpx.AsyncClient(timeout=40) as client:
        r = await client.post("https://api.voyageai.com/v1/embeddings", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()["data"]
    return [_norm(d["embedding"]) for d in data]

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
