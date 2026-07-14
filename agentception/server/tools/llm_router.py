from __future__ import annotations

"""One way in and out of every LLM call.

Before this, each caller constructed its own OpenAI client, and each one wrapped the
call in `except: pass`. When the OpenAI quota ran out the app kept working — quietly,
on heuristics, producing worse company names — and nothing anywhere said so. The 429s
were only visible by reading the server log.

Two rules here:

1. **Fallback is a decision, not an accident.** DeepSeek is primary (it works, and it
   is ~20x cheaper than GPT-4o); OpenAI is the fallback. When we fall back, we record
   *why*. When every provider fails, the caller gets an exception — not a silent None
   that turns into degraded output three layers up.
2. **Every call is priced.** Tokens in, tokens out, dollars, latency, and what it was
   for, written to `llm_calls`. "What does a search cost?" should be a query, not a
   guess.
"""

import os
import time
from dataclasses import dataclass
from typing import Optional

from ..memory import sql_store


@dataclass(frozen=True)
class Provider:
    name: str
    model: str
    base_url: Optional[str]
    api_key_env: str
    # USD per 1M tokens.
    cost_in: float
    cost_out: float

    def api_key(self) -> Optional[str]:
        key = (os.getenv(self.api_key_env) or "").strip()
        return key or None


# Order matters: this is the routing policy.
DEEPSEEK = Provider(
    name="deepseek", model=os.getenv("AGENTCEPTION_CHAT_MODEL", "deepseek-chat"),
    base_url="https://api.deepseek.com/v1", api_key_env="DEEPSEEK_API_KEY",
    cost_in=0.27, cost_out=1.10,
)
OPENAI = Provider(
    name="openai", model=os.getenv("AGENTCEPTION_OPENAI_FALLBACK_MODEL", "gpt-4o-mini"),
    base_url=None, api_key_env="OPENAI_API_KEY",
    cost_in=0.15, cost_out=0.60,
)

ROUTE = [DEEPSEEK, OPENAI]


class AllProvidersFailed(RuntimeError):
    """Every provider in the route failed. Callers must decide what to do — the one
    thing they must not do is pretend the call succeeded."""


@dataclass
class Completion:
    text: str
    provider: str
    model: str
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    fell_back: bool


def _price(provider: Provider, tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * provider.cost_in + tokens_out * provider.cost_out) / 1_000_000


async def complete(
    prompt: str,
    *,
    purpose: str,
    system: Optional[str] = None,
    max_tokens: int = 800,
    temperature: float = 0.0,
    json_mode: bool = False,
) -> Completion:
    """Run a chat completion through the route, recording cost.

    `purpose` is not decoration — it's the group-by that makes the cost dashboard
    answer "what is expensive?" instead of just "how much did we spend?".
    """
    import asyncio

    import openai

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    errors: list[str] = []

    for index, provider in enumerate(ROUTE):
        key = provider.api_key()
        if not key:
            errors.append(f"{provider.name}: no API key")
            continue

        started = time.monotonic()
        try:
            client = openai.OpenAI(api_key=key, base_url=provider.base_url, timeout=60.0)
            kwargs = {
                "model": provider.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await asyncio.to_thread(client.chat.completions.create, **kwargs)

            latency_ms = int((time.monotonic() - started) * 1000)
            usage = response.usage
            tokens_in = getattr(usage, "prompt_tokens", 0) or 0
            tokens_out = getattr(usage, "completion_tokens", 0) or 0
            cost = _price(provider, tokens_in, tokens_out)

            sql_store.llm_call_record(
                provider=provider.name, model=provider.model, purpose=purpose,
                tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost,
                latency_ms=latency_ms, ok=True,
            )

            if index > 0:
                print(f"↪️ LLM fell back to {provider.name} for '{purpose}': {'; '.join(errors)}")

            return Completion(
                text=(response.choices[0].message.content or "").strip(),
                provider=provider.name, model=provider.model,
                tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=cost,
                latency_ms=latency_ms, fell_back=index > 0,
            )

        except Exception as e:
            latency_ms = int((time.monotonic() - started) * 1000)
            response = getattr(e, "response", None)
            status = getattr(response, "status_code", None)
            detail = type(e).__name__ + (f" (HTTP {status})" if status else "")
            errors.append(f"{provider.name}: {detail}")

            sql_store.llm_call_record(
                provider=provider.name, model=provider.model, purpose=purpose,
                tokens_in=0, tokens_out=0, cost_usd=0.0, latency_ms=latency_ms,
                ok=False, error=detail,
            )
            # Try the next provider.

    raise AllProvidersFailed(f"all LLM providers failed for '{purpose}' — {'; '.join(errors)}")


def usage_summary(days: int = 7) -> dict:
    summary = sql_store.llm_usage_summary(days)
    summary["route"] = [
        {"provider": p.name, "model": p.model, "configured": bool(p.api_key())}
        for p in ROUTE
    ]
    return summary
