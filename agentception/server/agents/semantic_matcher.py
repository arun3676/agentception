from __future__ import annotations

import re
from typing import Dict, List


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    tokens = re.findall(r"[a-zA-Z0-9\+\#\.]+", text.lower())
    return [t for t in tokens if len(t) > 2]


def score_job_matches(resume_text: str, jobs: List[Dict]) -> List[Dict]:
    resume_tokens = set(_tokenize(resume_text))
    scored = []
    for job in jobs:
        job_text = " ".join([
            job.get("title", ""),
            job.get("snippet", ""),
            job.get("company", ""),
            job.get("location", ""),
        ])
        job_tokens = set(_tokenize(job_text))
        if not job_tokens:
            score = 0.0
        else:
            overlap = resume_tokens.intersection(job_tokens)
            score = round(len(overlap) / max(1, len(job_tokens)), 4)
        scored.append({**job, "match_score": score})
    scored.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    return scored
