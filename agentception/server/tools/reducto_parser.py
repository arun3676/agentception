from __future__ import annotations

"""Reducto-powered resume parsing.

Reducto (https://platform.reducto.ai) does layout-aware document parsing that
handles multi-column resumes, tables, and unusual layouts far better than
local text extraction. We use it for high-quality text extraction, then run
the existing structured parser over the clean text so the response schema
stays identical to the local pipeline.
"""

import os
import re
from typing import Any, Dict, Optional

import httpx

from .text_clean import strip_markdown

REDUCTO_BASE = "https://platform.reducto.ai"
_TIMEOUT = httpx.Timeout(60.0, connect=15.0)


def _api_key() -> Optional[str]:
    key = (os.getenv("REDUCTO_API_KEY") or "").strip()
    return key or None


def is_configured() -> bool:
    return _api_key() is not None


async def parse_resume_with_reducto(data: bytes, filename: str) -> Optional[Dict[str, Any]]:
    """Parse a resume PDF via Reducto. Returns {text, structured} or None on
    any failure so the caller can fall back to local extraction."""
    key = _api_key()
    if not key:
        return None

    headers = {"Authorization": f"Bearer {key}"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT, headers=headers) as client:
            # 1. Upload the document
            upload_resp = await client.post(
                f"{REDUCTO_BASE}/upload",
                files={"file": (filename or "resume.pdf", data, "application/pdf")},
            )
            upload_resp.raise_for_status()
            file_id = upload_resp.json().get("file_id")
            if not file_id:
                print("[Reducto] Upload returned no file_id")
                return None

            document_url = file_id if str(file_id).startswith("reducto://") else f"reducto://{file_id}"

            # 2. Parse synchronously
            parse_resp = await client.post(
                f"{REDUCTO_BASE}/parse",
                json={
                    "input": document_url,
                    "retrieval": {
                        "chunking": {"chunk_mode": "page"},
                        # Page-2 "Name (cont.)" banners otherwise parse as job entries
                        "filter_blocks": ["Header", "Footer", "Page Number"],
                    },
                },
            )
            parse_resp.raise_for_status()
            payload = parse_resp.json()

            markdown = await _extract_text(client, payload)
            if not markdown or not markdown.strip():
                print("[Reducto] Parse returned no text")
                return None

            text = markdown_to_plain_text(markdown)

            from .resume_parser import parse_resume_structured
            structured = parse_resume_structured(text)

            usage = payload.get("usage") or {}
            print(f"[Reducto] Parsed {filename}: {len(text)} chars, {usage.get('num_pages', '?')} pages")
            return {"text": text, "structured": structured}

    except httpx.HTTPStatusError as e:
        body = e.response.text[:200] if e.response is not None else ""
        print(f"[Reducto] HTTP {e.response.status_code if e.response else '?'}: {body}")
        return None
    except Exception as e:
        print(f"[Reducto] Parse failed: {e}")
        return None


# Page-continuation banners ("Arun Kumar Chukkala (cont.)") otherwise parse as job entries
_CONTINUATION_BANNER = re.compile(r"\(cont(?:inued)?\.?\)\s*$", re.IGNORECASE)


def _resume_heading(level: int, text: str) -> str:
    """resume_parser detects sections by casing. The H1 is the candidate's name,
    so it stays as written; deeper headers become the uppercase form it expects."""
    return text if level == 1 else text.upper()


def markdown_to_plain_text(markdown: str) -> str:
    """Flatten Reducto's markdown into the plain-text shape resume_parser expects."""
    text = strip_markdown(
        markdown,
        heading=_resume_heading,
        keep_urls=True,  # keeps GitHub/LinkedIn profile links findable
        bullet="• ",     # _parse_experience_entries keys off a "•" prefix
    )
    return "\n".join(l for l in text.split("\n") if not _CONTINUATION_BANNER.search(l))


async def _extract_text(client: httpx.AsyncClient, payload: Dict[str, Any]) -> str:
    """Pull the full text out of a Reducto parse response (full or url result)."""
    result = payload.get("result") or {}

    # Large results come back as a presigned URL instead of inline chunks
    if result.get("type") == "url" and result.get("url"):
        try:
            fetched = await client.get(result["url"], headers={})
            fetched.raise_for_status()
            result = fetched.json()
        except Exception as e:
            print(f"[Reducto] Failed to fetch url result: {e}")
            return ""

    chunks = result.get("chunks") or []
    parts = []
    for chunk in chunks:
        content = chunk.get("content") or chunk.get("embed") or ""
        if content.strip():
            parts.append(content.strip())
    return "\n\n".join(parts)


async def check_reducto() -> Dict[str, Any]:
    """Lightweight health check for the SystemHealth page."""
    key = _api_key()
    if not key:
        return {"configured": False, "ok": False, "status": "missing_key"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            resp = await client.post(
                f"{REDUCTO_BASE}/parse",
                headers={"Authorization": f"Bearer {key}"},
                json={},
            )
        # 422 (validation error on empty body) still proves the key is accepted
        if resp.status_code in (400, 422):
            return {"configured": True, "ok": True, "status": "ok"}
        if resp.status_code in (401, 403):
            return {"configured": True, "ok": False, "status": "unauthorized", "status_code": resp.status_code}
        return {"configured": True, "ok": resp.status_code < 500, "status_code": resp.status_code}
    except Exception as e:
        return {"configured": True, "ok": False, "status": "error", "error": str(e)[:120]}
