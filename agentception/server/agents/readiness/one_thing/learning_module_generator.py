"""
Generates a 14-day focused learning module from:
  - role_projects.json (pick project for the gap skill)
  - role_resources.json (pick 3 resources)
  - LLM generates daily plan

Max deadline: 14 days. No 12-week plans.
"""
from __future__ import annotations

import json
import os
from typing import Optional

from ....data.audit_prompts import LEARNING_MODULE_PROMPT


async def _call_llm(prompt: str, model: str = "gpt-4o-mini") -> str:
    import httpx
    api_key = os.getenv("OPENAI_API_KEY", "")
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


def _parse_json(text: str) -> dict:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1] if "\n" in clean else clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    clean = clean.strip()
    if clean.startswith("json"):
        clean = clean[4:].strip()
    try:
        return json.loads(clean)
    except json.JSONDecodeError:
        return {"_raw": text, "module_title": "Learning Module", "daily_plan": []}


def _load_data_file(name: str) -> dict | list:
    """Load a JSON data file from the learning-path bridge."""
    try:
        from ....bridge import data_file
        path = data_file(name)
        if path:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _fallback_module(gap_skill: str, target_role: str, resources: list, project_ideas: list) -> dict:
    """Return a useful, deterministic sprint when the LLM provider is unavailable."""
    project = project_ideas[0]
    project_title = project.get("title", f"Build a {gap_skill} Portfolio Project") if isinstance(project, dict) else str(project)
    project_description = project.get("description", "Create a small, reviewable proof project.") if isinstance(project, dict) else "Create a small, reviewable proof project."
    return {
        "gap_skill": gap_skill,
        "module_title": f"14-Day {gap_skill} Sprint",
        "deadline_days": 14,
        "project": {"title": project_title, "description": project_description},
        "resources": resources[:5],
        "daily_plan": [
            {"day": day, "focus": focus}
            for day, focus in enumerate([
                f"Define the {gap_skill} outcome and success metric.",
                "Study the core concepts and capture concise notes.",
                "Reproduce one minimal working example.",
                "Implement the first project component.",
                "Add tests and document assumptions.",
                "Improve quality using a measurable evaluation.",
                "Review the first week and reduce scope where needed.",
                "Implement the second project component.",
                "Add realistic inputs and edge cases.",
                "Measure results and record before/after evidence.",
                "Refactor for clarity and reliability.",
                "Write a short technical case study.",
                "Practice explaining the project for a hiring conversation.",
                f"Publish the {target_role} proof project and add it to your resume.",
            ], start=1)
        ],
        "source": "deterministic_fallback",
    }


async def generate_learning_module(
    *,
    gap_skill: str,
    target_role: str,
    current_level: str = "beginner",
) -> dict:
    """Generate a 14-day learning module for a specific skill gap."""

    # Load project ideas and resources from learning-path data
    projects_data = _load_data_file("role_projects.json")
    resources_data = _load_data_file("role_resources.json")

    # Find relevant projects
    project_ideas = []
    if isinstance(projects_data, dict):
        for role_key, projects in projects_data.items():
            if target_role.lower() in role_key.lower() or gap_skill.lower() in role_key.lower():
                if isinstance(projects, list):
                    project_ideas.extend(projects[:3])
                break

    # Find relevant resources
    resources = []
    if isinstance(resources_data, dict):
        for role_key, res_list in resources_data.items():
            if target_role.lower() in role_key.lower() or gap_skill.lower() in role_key.lower():
                if isinstance(res_list, list):
                    resources.extend(res_list[:5])
                break

    # Fall back to generic suggestions if no data found
    if not project_ideas:
        project_ideas = [
            {"title": f"Build a {gap_skill} Portfolio Project", "description": f"Hands-on project demonstrating {gap_skill}"}
        ]
    if not resources:
        resources = [
            {"title": f"{gap_skill} Crash Course", "url": "https://www.youtube.com", "type": "video"},
            {"title": f"{gap_skill} Documentation", "url": "https://docs.python.org", "type": "article"},
        ]

    prompt = LEARNING_MODULE_PROMPT.format(
        gap_skill=gap_skill,
        target_role=target_role,
        current_level=current_level,
        project_ideas=json.dumps(project_ideas[:3], default=str),
        resources=json.dumps(resources[:5], default=str),
    )

    try:
        resp = await _call_llm(prompt)
        module = _parse_json(resp)
    except Exception as exc:
        print(f"[learning_module] LLM unavailable, using deterministic fallback: {exc}")
        module = _fallback_module(gap_skill, target_role, resources, project_ideas)

    # Ensure required fields exist
    module.setdefault("gap_skill", gap_skill)
    module.setdefault("module_title", f"14-Day {gap_skill} Sprint")
    module.setdefault("deadline_days", 14)

    return module
