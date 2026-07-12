from __future__ import annotations
import re
from typing import Dict, Any, List, Optional, Tuple

from ..rag.match import _embed, _cos, _get_voyage_key  # Reuse existing Voyage embedding helper

STOPWORDS = {
    "the","a","an","and","or","for","in","on","to","with","of","at","by","from","as",
    "we","you","your","our","their","they","be","is","are","was","were","will","can",
    "ai","job","jobs","open","opening","role","apply","company","hiring","join",
    "san","francisco","ca","sf","usa","us","remote","hybrid","onsite"
}


def _tokenize(text: str) -> List[str]:
    raw = re.findall(r"[a-zA-Z][a-zA-Z0-9\-\+\.]{1,}", text.lower())
    return [t for t in raw if len(t) >= 3 and t not in STOPWORDS]


def _collect_skill_candidates(resume_insights: Dict[str, Any]) -> List[str]:
    skills = resume_insights.get("skills_flat") or resume_insights.get("skills") or []
    if isinstance(skills, dict):
        flat = []
        for v in skills.values():
            flat.extend(v)
        skills = flat
    tech_stack = resume_insights.get("tech_stack") or []
    domains = resume_insights.get("domains") or []
    candidates = list({s.lower() for s in skills + tech_stack + domains if isinstance(s, str)})
    return candidates


def compute_keyword_match(job_description: str, resume_text: str, resume_insights: Dict[str, Any]) -> Tuple[float, List[str]]:
    """
    Keyword overlap with stopword filtering; enriched with tech_stack/domains.
    """
    jd_tokens = set(_tokenize(job_description))
    skill_candidates = _collect_skill_candidates(resume_insights)
    skill_tokens = {s for s in skill_candidates if len(s) >= 3 and s not in STOPWORDS}
    matched = sorted(skill_tokens & jd_tokens)
    if not skill_tokens:
        return 0.0, []
    score = min(100.0, (len(matched) / max(1, len(skill_tokens))) * 100.0)
    return score, matched


async def compute_semantic_similarity(resume_text: str, job_description: str) -> float | None:
    """Semantic similarity (0-100) via Voyage embeddings.

    Returns **None** when the signal is genuinely unavailable (no key, provider
    down). Returning 0.0 instead — as this used to — is a lie: it means "these
    documents are unrelated", so a rate-limit quietly became a bad match score and
    the hybrid matcher silently degraded to keyword-only.
    """
    if not _get_voyage_key():
        return None
    try:
        vecs = await _embed([resume_text, job_description])
        if len(vecs) < 2:
            return None
        return max(0.0, _cos(vecs[0], vecs[1])) * 100.0
    except Exception as e:
        print(f"⚠️ semantic similarity unavailable: {type(e).__name__}: {str(e)[:100]}")
        return None


KEYWORD_WEIGHT = 0.4
SEMANTIC_WEIGHT = 0.6


async def compute_match_scores(
    resume_text: str, job_descriptions: List[str], resume_insights: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Score a resume against many jobs in ONE embedding call.

    Scoring each job separately meant one Voyage request per job — 10 requests for a
    normal search. Voyage rate-limits per minute, so they 429'd, backed off 5s → 11s →
    21s → 41s each, and a search that should take seconds took minutes.

    Voyage accepts a list. Embed [resume, jd1, jd2, ...] once and take cosines against
    the first vector: 1 request instead of N, no rate limit, no backoff.
    """
    if not job_descriptions:
        return []

    semantic: List[Optional[float]] = [None] * len(job_descriptions)

    if _get_voyage_key():
        try:
            vectors = await _embed([resume_text] + list(job_descriptions))
            resume_vec, job_vecs = vectors[0], vectors[1:]
            semantic = [max(0.0, _cos(resume_vec, v)) * 100.0 for v in job_vecs]
        except Exception as e:
            print(f"⚠️ semantic similarity unavailable for this batch: {type(e).__name__}: {str(e)[:100]}")

    from .match_calibration import calibrated_match

    results: List[Dict[str, Any]] = []
    for jd, sem in zip(job_descriptions, semantic):
        keyword_score, matched = compute_keyword_match(jd, resume_text, resume_insights)

        if sem is None:
            final = keyword_score
            signals = ["keyword"]
        else:
            final = KEYWORD_WEIGHT * keyword_score + SEMANTIC_WEIGHT * sem
            signals = ["keyword", "semantic"]
        final = max(0.0, min(100.0, final))

        missing = analyze_gaps(jd, resume_insights)["missing_skills"]
        cal = calibrated_match(final, matched, missing, signals)

        results.append({
            "match_score": round(final, 1),
            "match_probability": cal.probability,
            "match_band": cal.band,
            "match_explanation": cal.explanation,
            "score_breakdown": {
                "keyword": round(keyword_score, 1),
                "semantic": round(sem, 1) if sem is not None else None,
            },
            "signals": signals,
            "matched_keywords": matched,
            "missing_skills": missing,
        })

    return results


async def compute_match_score(
    resume_text: str, job_description: str, resume_insights: Dict[str, Any]
) -> Dict[str, Any]:
    """Hybrid score: keyword overlap + semantic similarity.

    When the semantic signal is unavailable we fall back to keyword-only and *say
    so* (`semantic: null`, `signals: ["keyword"]`). The previous version returned a
    hardcoded 5.0 whenever scoring failed — a number the UI then showed as if it
    meant something. A failed match is now reported as a failed match.
    """
    keyword_score, matched_keywords = compute_keyword_match(
        job_description, resume_text, resume_insights
    )
    semantic_score = await compute_semantic_similarity(resume_text, job_description)

    if semantic_score is None:
        final_score = keyword_score
        signals = ["keyword"]
    else:
        final_score = KEYWORD_WEIGHT * keyword_score + SEMANTIC_WEIGHT * semantic_score
        signals = ["keyword", "semantic"]

    final_score = max(0.0, min(100.0, final_score))

    # A raw "43.9" reads like "you are 44% qualified", which is not what it measures.
    # Calibrate it into P(this job is a genuine fit), fitted on the labelled pairs,
    # then band it — nobody can act on the difference between 61% and 64%.
    from .match_calibration import calibrated_match

    missing = analyze_gaps(job_description, resume_insights)["missing_skills"]
    calibrated = calibrated_match(final_score, matched_keywords, missing, signals)

    return {
        "match_score": round(final_score, 1),
        "match_probability": calibrated.probability,
        "match_band": calibrated.band,
        "match_explanation": calibrated.explanation,
        "score_breakdown": {
            "keyword": round(keyword_score, 1),
            "semantic": round(semantic_score, 1) if semantic_score is not None else None,
        },
        "signals": signals,
        "matched_keywords": matched_keywords,
        "missing_skills": missing,
    }


def extract_jd_skills(job_description: str) -> List[str]:
    """Skills the job actually asks for, matched against the O*NET-based taxonomy.

    Two prior versions of this were wrong in opposite directions: the first returned
    every unseen token (so "equity" and "offers" became "missing skills" and fed the
    study drawer); the second used a 77-word hardcoded list, which was precise but
    capped recall at 0.365 — it could not name a skill it had never heard of.
    """
    from .skill_extractor import extract_skills

    return extract_skills(job_description)


def analyze_gaps(job_description: str, resume_insights: Dict[str, Any]) -> Dict[str, Any]:
    """Skills the job requires that the resume doesn't evidence."""
    jd_skills = extract_jd_skills(job_description)
    have = {s.lower() for s in _collect_skill_candidates(resume_insights)}

    missing = [s for s in jd_skills if s.lower() not in have][:15]
    suggestions = [
        f"{s} appears in this job description but not in your resume."
        for s in missing[:10]
    ]
    return {
        "missing_skills": missing,
        "suggestions": suggestions,
    }

