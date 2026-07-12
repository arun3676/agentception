from __future__ import annotations

from typing import Any, Dict, Optional

from .skill_gap_agent import analyze_skill_gaps, recommend_resources_for_skills
from ..learning_path_service import generate_learning_path
from ..schemas import LearningPathRequest


def run_orchestration(task: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified orchestration entrypoint for learning, skill gaps, and job workflows.
    """
    task = task.strip().lower()
    if task == "learning_path":
        req = LearningPathRequest(**payload)
        path = generate_learning_path(req)
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
