from __future__ import annotations

import datetime as dt
import math
import uuid
from typing import List

from .schemas import LearningMilestone, LearningPath, LearningPathRequest, LearningResourceItem
from .memory import sql_store
from .resources_library import ensure_resources_seeded


_MILESTONE_TITLES = [
    "Foundations",
    "Core Concepts",
    "Applied Projects",
    "Advanced Topics",
]


def _estimate_total_hours(time_commitment: str) -> int:
    mapping = {
        "minimal": 20,
        "moderate": 40,
        "substantial": 80,
        "intensive": 120,
    }
    return mapping.get(time_commitment.lower(), 40)


def _select_resources(topic: str, max_items: int = 12) -> List[LearningResourceItem]:
    ensure_resources_seeded()
    resources = sql_store.resources_list(query=topic, limit=max_items, offset=0)
    if len(resources) < max_items:
        featured = sql_store.resources_featured(limit=max_items)
        combined = resources + [r for r in featured if r.get("id") not in {x.get("id") for x in resources}]
        resources = combined[:max_items]
    return [
        LearningResourceItem(
            id=r.get("id"),
            title=r.get("title") or "Resource",
            url=r.get("url") or "",
            description=r.get("description"),
            category=r.get("category"),
            tags=r.get("tags") or [],
        )
        for r in resources
        if r.get("url")
    ]


def _build_milestones(topic: str, resources: List[LearningResourceItem], total_hours: int) -> List[LearningMilestone]:
    if not resources:
        resources = [
            LearningResourceItem(
                id=None,
                title="AI Resource Library",
                url="https://huggingface.co/",
                description="Browse curated AI resources to get started.",
                category="service",
                tags=["ai", "resources"],
            )
        ]
    per_milestone = max(1, math.ceil(len(resources) / len(_MILESTONE_TITLES)))
    milestones: List[LearningMilestone] = []
    hours_per = max(5, int(total_hours / max(1, len(_MILESTONE_TITLES))))
    for idx, title in enumerate(_MILESTONE_TITLES):
        start = idx * per_milestone
        end = start + per_milestone
        chunk = resources[start:end]
        if not chunk:
            continue
        milestones.append(
            LearningMilestone(
                title=f"{title} - {topic}",
                description=f"Build {title.lower()} skills in {topic} with curated AI resources.",
                estimated_hours=hours_per,
                resources=chunk,
                skills_gained=[topic, "AI fundamentals", f"{title.lower()} mastery"],
            )
        )
    return milestones


def generate_learning_path(req: LearningPathRequest) -> LearningPath:
    path_id = str(uuid.uuid4())
    total_hours = _estimate_total_hours(req.time_commitment)
    resources = _select_resources(req.topic)
    milestones = _build_milestones(req.topic, resources, total_hours)
    title = f"{req.topic} Learning Path"
    description = (
        f"AI-first learning path for {req.topic}. Each milestone links to curated resources "
        "from the AI Resource Library."
    )
    path = LearningPath(
        id=path_id,
        title=title,
        description=description,
        topic=req.topic,
        expertise_level=req.expertise_level,
        learning_style=req.learning_style,
        time_commitment=req.time_commitment,
        goals=req.goals,
        milestones=milestones,
        total_hours=total_hours,
        created_at=dt.datetime.utcnow().isoformat(),
    )
    sql_store.learning_path_save(
        path_id=path_id,
        user_id=req.user_id,
        title=title,
        topic=req.topic,
        expertise_level=req.expertise_level,
        path_json=path.model_dump(),
    )
    return path
