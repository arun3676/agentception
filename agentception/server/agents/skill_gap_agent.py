from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..memory import sql_store
from ..resources_library import ensure_resources_seeded


COMMON_SKILLS = [
    "python", "pytorch", "tensorflow", "scikit-learn", "numpy", "pandas",
    "llm", "rag", "vector database", "pinecone", "weaviate", "qdrant", "chroma",
    "langchain", "langgraph", "llamaindex", "crewai", "autogen",
    "docker", "kubernetes", "mlops", "fastapi", "flask",
    "react", "next.js", "typescript", "postgresql", "redis",
    "aws", "gcp", "azure", "cloud", "monitoring", "observability",
]

ROLE_SKILLS = {
    "ai engineer": ["python", "llm", "rag", "vector database", "mlops", "docker"],
    "ml engineer": ["python", "pytorch", "tensorflow", "mlops", "docker", "kubernetes"],
    "data scientist": ["python", "pandas", "scikit-learn", "ml", "statistics"],
    "full stack": ["react", "typescript", "fastapi", "postgresql", "redis"],
}


def _extract_skills(text: str) -> List[str]:
    if not text:
        return []
    lower = text.lower()
    found = []
    for skill in COMMON_SKILLS:
        if skill in lower:
            found.append(skill)
    return sorted(set(found))


def _skills_for_role(role: Optional[str]) -> List[str]:
    if not role:
        return []
    key = role.strip().lower()
    return ROLE_SKILLS.get(key, [])


def analyze_skill_gaps(
    resume_text: str,
    job_text: Optional[str] = None,
    target_role: Optional[str] = None,
) -> Dict[str, List[str]]:
    resume_skills = set(_extract_skills(resume_text))
    target_skills = set(_extract_skills(job_text or "")) if job_text else set(_skills_for_role(target_role))
    missing = sorted(s for s in target_skills if s not in resume_skills)
    return {
        "resume_skills": sorted(resume_skills),
        "target_skills": sorted(target_skills),
        "missing_skills": missing,
    }


def recommend_resources_for_skills(skills: List[str], per_skill: int = 3) -> Dict[str, List[dict]]:
    ensure_resources_seeded()
    recommendations: Dict[str, List[dict]] = {}
    for skill in skills:
        resources = sql_store.resources_list(query=skill, limit=per_skill, offset=0)
        recommendations[skill] = resources
    return recommendations
