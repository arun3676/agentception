from __future__ import annotations

from typing import Any, Dict, Optional

from .skill_gap_agent import analyze_skill_gaps, recommend_resources_for_skills
from ..learning_path_service import generate_learning_path
from ..schemas import LearningPathRequest


def run_orchestration(task: str, payload: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Unified orchestration entrypoint for learning, skill gaps, and job workflows.

    `user_id` must be supplied for tasks that persist user-owned rows. This entry
    point is currently unmounted; the argument is here so that whoever wires it up
    has to pass a real owner rather than silently creating an unowned learning path.
    """
    task = task.strip().lower()
    if task == "learning_path":
        if not user_id:
            return {"error": "learning_path requires an authenticated user_id"}
        req = LearningPathRequest(**payload)
        path = generate_learning_path(req, user_id=user_id)
        return {"path": path.model_dump()}
    if task == "skill_gap":
        analysis = analyze_skill_gaps(
            resume_text=payload.get("resume_text", ""),
            job_text=payload.get("job_text"),
            target_role=payload.get("target_role"),
        )
        recommendations = recommend_resources_for_skills(analysis["missing_skills"])
        return {"analysis": analysis, "recommendations": recommendations}
    return {"error": f"Unknown task: {task}"}
