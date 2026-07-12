"""LLM routing and cost accounting.

The behaviour under test is mostly about *not lying*: fall back on purpose, record
what it cost, and raise when everything fails instead of returning an empty string
that the caller mistakes for "the page was blank".
"""

import asyncio

import pytest

from server.memory import sql_store
from server.tools import llm_router
from server.tools.llm_router import AllProvidersFailed, Provider, _price, complete


class FakeUsage:
    def __init__(self, prompt_tokens, completion_tokens):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


class FakeResponse:
    def __init__(self, text, tin=100, tout=50):
        self.choices = [type("C", (), {"message": type("M", (), {"content": text})()})()]
        self.usage = FakeUsage(tin, tout)


def _fake_openai(monkeypatch, behaviour):
    """behaviour: dict of base_url -> callable(**kwargs) -> FakeResponse | raises."""

    class FakeClient:
        def __init__(self, api_key=None, base_url=None, timeout=None):
            self.base_url = base_url
            self.chat = type("Chat", (), {"completions": self})()

        def create(self, **kwargs):
            return behaviour(self.base_url, **kwargs)

    monkeypatch.setattr(llm_router, "openai", type("M", (), {"OpenAI": FakeClient}), raising=False)

    import openai as real_openai

    monkeypatch.setattr(real_openai, "OpenAI", FakeClient)


class TestPricing:
    def test_prices_per_million_tokens(self):
        p = Provider("x", "m", None, "K", cost_in=1.0, cost_out=2.0)
        # 1M in @ $1 + 1M out @ $2
        assert _price(p, 1_000_000, 1_000_000) == pytest.approx(3.0)

    def test_small_calls_cost_almost_nothing(self):
        assert _price(llm_router.DEEPSEEK, 1000, 500) < 0.01


class TestRouting:
    def test_uses_the_primary_when_it_works(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        _fake_openai(monkeypatch, lambda base_url, **kw: FakeResponse("primary answer"))

        result = asyncio.run(complete("hi", purpose="test"))
        assert result.provider == "deepseek"
        assert result.fell_back is False
        assert result.text == "primary answer"

    def test_falls_back_when_the_primary_fails(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
        monkeypatch.setenv("OPENAI_API_KEY", "k")

        def behaviour(base_url, **kw):
            if base_url:  # deepseek
                raise RuntimeError("429 insufficient_quota")
            return FakeResponse("fallback answer")

        _fake_openai(monkeypatch, behaviour)

        result = asyncio.run(complete("hi", purpose="test"))
        assert result.provider == "openai"
        assert result.fell_back is True

    def test_raises_when_every_provider_fails(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
        monkeypatch.setenv("OPENAI_API_KEY", "k")

        def behaviour(base_url, **kw):
            raise RuntimeError("boom")

        _fake_openai(monkeypatch, behaviour)

        # The whole point: a total failure must not look like an empty answer.
        with pytest.raises(AllProvidersFailed):
            asyncio.run(complete("hi", purpose="test"))

    def test_skips_providers_with_no_key(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "k")
        _fake_openai(monkeypatch, lambda base_url, **kw: FakeResponse("openai only"))

        result = asyncio.run(complete("hi", purpose="test"))
        assert result.provider == "openai"


class TestCostRecording:
    def test_every_call_is_recorded_with_its_cost(self, monkeypatch):
        sql_store.init()
        monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
        _fake_openai(monkeypatch, lambda base_url, **kw: FakeResponse("ok", tin=1000, tout=500))

        before = sql_store.llm_usage_summary(days=1)["calls"]
        asyncio.run(complete("hi", purpose="unit_test_purpose"))
        after = sql_store.llm_usage_summary(days=1)

        assert after["calls"] == before + 1
        assert any(p["purpose"] == "unit_test_purpose" for p in after["by_purpose"])

    def test_failures_are_recorded_too(self, monkeypatch):
        sql_store.init()
        monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
        monkeypatch.setenv("OPENAI_API_KEY", "")

        def behaviour(base_url, **kw):
            raise RuntimeError("quota")

        _fake_openai(monkeypatch, behaviour)

        before = sql_store.llm_usage_summary(days=1)["failures"]
        with pytest.raises(AllProvidersFailed):
            asyncio.run(complete("hi", purpose="test"))

        # A silent failure is the thing we're trying to make impossible.
        assert sql_store.llm_usage_summary(days=1)["failures"] == before + 1
