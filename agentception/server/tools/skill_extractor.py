from __future__ import annotations

"""Skill extraction against a real taxonomy.

The previous extractor scanned for ~77 hardcoded keywords. Measured on 69 real job
descriptions, that capped recall at **0.365** — only 48 of the 309 distinct skills
those postings asked for were even *in* the list. No amount of tuning fixes a
vocabulary problem; you change the vocabulary.

This uses O*NET (7.5k real technology names) plus a curated layer for concepts
O*NET's product catalogue misses (RAG, MLOps, distributed systems). Matching is a
gazetteer pass: word-boundary, case-insensitive, longest-match-wins, with an alias
table so "k8s" and "Kubernetes" collapse to one skill.

Deliberately NOT an LLM call: extraction runs on every job in every search, so a
per-JD LLM round-trip would add cost and latency to the hot path. The taxonomy pass
is free, instant, and deterministic — and the eval says it's enough.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable

_TAXONOMY_PATH = Path(__file__).parent.parent / "data" / "skills" / "tech_skills.json"

# Written forms that should resolve to one canonical skill.
_ALIASES: dict[str, str] = {
    "k8s": "Kubernetes",
    "golang": "Go",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node js": "Node.js",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "psql": "PostgreSQL",
    "js": "JavaScript",
    "ts": "TypeScript",
    "py": "Python",
    "gcp": "Google Cloud Platform",
    "aws": "AWS",
    "amazon web services": "AWS",
    "ml": "Machine Learning",
    "dl": "Deep Learning",
    "nlp": "NLP",
    "llms": "LLM",
    "large language model": "LLM",
    "large language models": "LLM",
    "retrieval augmented generation": "RAG",
    "retrieval-augmented generation": "RAG",
    "vector db": "Vector Database",
    "vector databases": "Vector Database",
    "vector stores": "Vector Database",
    "ci cd": "CI/CD",
    "cicd": "CI/CD",
    "rest apis": "REST API",
    "restful apis": "REST API",
    "restful api": "REST API",
    "iac": "Infrastructure as Code",
    "sre": "Site Reliability Engineering",
    "tf": "Terraform",
    "k8": "Kubernetes",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
}

# Skill names that are also ordinary English. Matched bare they are pure false
# positives — "the rest of the team" became REST, "go to production" became Go.
# These only count when the surrounding text looks like a technology list.
_AMBIGUOUS = {
    "go", "r", "c", "rust", "swift", "scala", "julia", "dart", "elm", "nim",
    "rest", "agent", "agents", "bi", "ray", "spark", "flink", "prime", "vault",
    "glue", "athena", "lambda", "expo", "polars", "triton", "cursor", "copilot",
}


@lru_cache(maxsize=1)
def _load_taxonomy() -> tuple[dict[str, str], re.Pattern]:
    """Returns (lowercase_name -> canonical_name, compiled matcher)."""
    data = json.loads(_TAXONOMY_PATH.read_text(encoding="utf-8"))
    canonical: dict[str, str] = {s["name"].lower(): s["name"] for s in data["skills"]}

    for alias, target in _ALIASES.items():
        canonical.setdefault(alias, target)

    # Longest first so "Apache Airflow" wins over "Apache", and "REST API" over "REST".
    terms = sorted(canonical, key=len, reverse=True)
    pattern = re.compile(
        r"(?<![\w/.-])(" + "|".join(re.escape(t) for t in terms) + r")(?![\w/-])",
        re.IGNORECASE,
    )
    return canonical, pattern


def _looks_like_a_skill_mention(text: str, start: int, end: int) -> bool:
    """Guard for single-letter/common-word skills ('Go', 'R', 'C')."""
    window = text[max(0, start - 30) : min(len(text), end + 30)].lower()
    return bool(
        re.search(r"[,/|()]|\b(experience|proficien|program|language|stack|skill|using|knowledge)\b", window)
    )


def extract_skills(text: str, limit: int = 40) -> list[str]:
    """Canonical skill names the text mentions, most-specific first."""
    if not text:
        return []

    canonical, pattern = _load_taxonomy()
    found: dict[str, int] = {}

    for m in pattern.finditer(text):
        raw = m.group(1)
        low = raw.lower()

        if low in _AMBIGUOUS and not _looks_like_a_skill_mention(text, m.start(), m.end()):
            continue

        name = canonical.get(low, raw)
        found[name] = found.get(name, 0) + 1

    # Frequency is a decent proxy for how central a skill is to the posting.
    ordered = sorted(found.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    return [name for name, _ in ordered[:limit]]


def taxonomy_size() -> int:
    canonical, _ = _load_taxonomy()
    return len(canonical)


def canonicalise(skills: Iterable[str]) -> list[str]:
    """Map arbitrary skill strings onto taxonomy names where possible."""
    canonical, _ = _load_taxonomy()
    out, seen = [], set()
    for s in skills:
        name = canonical.get(s.strip().lower(), s.strip())
        if name and name.lower() not in seen:
            seen.add(name.lower())
            out.append(name)
    return out
