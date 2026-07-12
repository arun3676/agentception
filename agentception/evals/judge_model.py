"""DeepSeek as the DeepEval judge model.

DeepEval defaults to OpenAI. Two reasons not to use it here: the project's OpenAI
quota is exhausted (429s in production logs), and DeepSeek is an order of magnitude
cheaper for judging. The judge is pinned to one model on purpose — swapping judges
silently changes every score in the report.
"""

from __future__ import annotations

import os

from deepeval.models import DeepEvalBaseLLM

JUDGE_MODEL = "deepseek-chat"  # pinned: changing this invalidates historical scores


class DeepSeekJudge(DeepEvalBaseLLM):
    def __init__(self, model: str = JUDGE_MODEL):
        self.model_name = model
        self._client = None

    def load_model(self):
        if self._client is None:
            import openai

            key = os.getenv("DEEPSEEK_API_KEY")
            if not key:
                raise RuntimeError("DEEPSEEK_API_KEY not set")
            self._client = openai.OpenAI(
                api_key=key, base_url="https://api.deepseek.com/v1", timeout=90.0
            )
        return self._client

    def generate(self, prompt: str, schema=None):
        client = self.load_model()
        kwargs = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,  # deterministic judging
        }
        if schema is not None:
            kwargs["response_format"] = {"type": "json_object"}

        content = client.chat.completions.create(**kwargs).choices[0].message.content or ""

        if schema is not None:
            import json

            cleaned = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
            return schema(**json.loads(cleaned))
        return content

    async def a_generate(self, prompt: str, schema=None):
        import asyncio

        return await asyncio.to_thread(self.generate, prompt, schema)

    def get_model_name(self) -> str:
        return self.model_name
