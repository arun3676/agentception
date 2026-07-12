"""
Kimi API wrapper (~30 lines).
Kimi (Moonshot AI) excels at long-context analysis — perfect for
sending [resume + 20 JDs] in a single call.

Falls back to OpenAI if KIMI_API_KEY is not set.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx

KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")
KIMI_BASE_URL = "https://api.moonshot.cn/v1"


async def kimi_analyze(
    prompt: str,
    model: str = "moonshot-v1-128k",
    temperature: float = 0.3,
    fallback_model: str = "gpt-4o-mini",
) -> str:
    """
    Send a long-context prompt to Kimi. Falls back to OpenAI if Kimi is unavailable.
    """
    if KIMI_API_KEY:
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                resp = await client.post(
                    f"{KIMI_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {KIMI_API_KEY}"},
                    json={
                        "model": model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"⚠️ Kimi API failed ({e}), falling back to OpenAI")

    # Fallback to OpenAI
    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key:
        raise RuntimeError("Neither KIMI_API_KEY nor OPENAI_API_KEY is set")

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {openai_key}"},
            json={
                "model": fallback_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
