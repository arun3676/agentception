"""Is the study material we surface actually about the thing the user clicked?

LLM-as-judge (DeepEval GEval). Marked `judge`: it costs money and is
non-deterministic, so it runs nightly, not on every push. Following the standard
guidance for CI-safe LLM evals: pin the judge model, keep the input set stable,
and gate on a tolerance band rather than an exact threshold.
"""

from __future__ import annotations

import asyncio
import os

import pytest

pytestmark = [pytest.mark.judge]

# The topics a user actually clicks from a gap chip.
TOPICS = [
    ("RAG", "ai_engineer"),
    ("Kubernetes", "devops_engineer"),
    ("Airflow", "data_engineer"),
    ("React", "frontend_engineer"),
]

MIN_RELEVANCE = 0.75
TOLERANCE = 0.05  # band, so judge jitter alone can't fail the build


@pytest.mark.skipif(
    not os.getenv("DEEPSEEK_API_KEY"), reason="DEEPSEEK_API_KEY not set (judge model)"
)
def test_study_results_are_relevant(record_property, capsys):
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCase, LLMTestCaseParams

    from evals.judge_model import DeepSeekJudge
    from server.routers.study import _level_data, _search_web, resolve_pillar

    judge = DeepSeekJudge()

    metric = GEval(
        name="Study relevance",
        criteria=(
            "Given a TOPIC in the input, decide whether the retrieved resource in the "
            "output is genuinely learning material ABOUT that topic. A resource that "
            "merely mentions the topic in passing, or that is a job ad, product page, "
            "or unrelated tutorial, is NOT relevant."
        ),
        evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
        model=judge,
        threshold=MIN_RELEVANCE,
    )

    async def fetch(topic: str, role: str):
        pillar = resolve_pillar(topic, role)
        level_data = _level_data(pillar["key"], "intermediate")
        return await _search_web(topic, "intermediate", level_data, pillar)

    scores: list[float] = []
    for topic, role in TOPICS:
        results = asyncio.run(fetch(topic, role))[:3]
        for res in results:
            title = res.get("title") or ""
            snippet = " ".join(res.get("highlights") or [])[:300]
            if not title:
                continue
            case = LLMTestCase(
                input=f"TOPIC: {topic}",
                actual_output=f"{title}\n{snippet}",
            )
            metric.measure(case)
            scores.append(metric.score)

    if not scores:
        pytest.skip("no study results returned (search provider unavailable)")

    mean = sum(scores) / len(scores)
    with capsys.disabled():
        print(f"\n  study relevance (judge, n={len(scores)} resources): {mean:.3f}")

    record_property("study_relevance", round(mean, 4))

    assert mean >= MIN_RELEVANCE - TOLERANCE, (
        f"study relevance {mean:.3f} below {MIN_RELEVANCE} (±{TOLERANCE})"
    )
