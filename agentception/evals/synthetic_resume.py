"""Deterministic, visibly synthetic resume fixtures used by offline tests.

The canonical source contains no real person's resume or career history. Generated
PDFs are temporary Playwright inputs and are never committed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evals.pii import assert_synthetic_fixture_text

FIXTURE_SOURCE = Path(__file__).resolve().parent / "fixtures" / "synthetic_resume.json"
SYNTHETIC_FILENAME = "synthetic-jordan-lee.pdf"


def load_synthetic_resume() -> dict[str, Any]:
    data = json.loads(FIXTURE_SOURCE.read_text(encoding="utf-8"))
    assert_synthetic_fixture_text(json.dumps(data, ensure_ascii=False))
    return data


def render_resume_text(data: dict[str, Any] | None = None) -> str:
    """Render the canonical source to stable plain text for ranking evals."""
    data = data or load_synthetic_resume()
    contact = data["contact"]
    skills = data["skills"]

    lines = [
        contact["name"],
        data["fixture_notice"],
        " | ".join(
            [
                f'{contact["city"]}, {contact["state"]}, {contact["country"]}',
                contact["email"],
                contact["phone"],
                contact["website"],
            ]
        ),
        "",
        "PROFESSIONAL SUMMARY",
        data["summary"],
        "",
        "TECHNICAL SKILLS",
        "Technical: " + ", ".join(skills["technical"]),
        "Collaboration: " + ", ".join(skills["soft"]),
        "",
        "PROFESSIONAL EXPERIENCE",
    ]

    for experience in data["experience"]:
        duration = experience["duration"]
        lines.extend(
            [
                (
                    f'{experience["position"]}, {experience["company"]} - '
                    f'{experience["location"]}'
                ),
                f'{duration["start"]} - {duration["end"]}',
                *[f"- {item}" for item in experience["achievements"]],
                "",
            ]
        )

    lines.append("FEATURED PROJECTS")
    for project in data["projects"]:
        lines.append(project["name"])
        lines.extend(f"- {item}" for item in project["description"])
        for link_key in ("github", "demo"):
            if project.get(link_key):
                lines.append(project[link_key])
        lines.append("")

    lines.append("EDUCATION")
    for education in data["education"]:
        duration = education["duration"]
        lines.extend(
            [
                (
                    f'{education["degree"]} in {education["field"]}, '
                    f'{education["institution"]}'
                ),
                f'{education["location"]} | {duration["start"]} - {duration["end"]}',
            ]
        )

    if data["certifications"]:
        lines.extend(["", "CERTIFICATIONS"])
        for certification in data["certifications"]:
            lines.append(
                f'{certification["name"]} | {certification["issuer"]} | '
                f'{certification["dateObtained"]}'
            )

    text = "\n".join(lines).strip() + "\n"
    assert_synthetic_fixture_text(text)
    return text


def build_structured_parse(data: dict[str, Any] | None = None) -> dict[str, Any]:
    """Translate the canonical source into the parser snapshot schema."""
    data = data or load_synthetic_resume()
    contact = data["contact"]
    parsed = {
        "contact": {
            "name": contact["name"],
            "email": contact["email"],
            "location": f'{contact["city"]}, {contact["state"]}, {contact["country"]}',
        },
        "summary": data["summary"],
        "experience": [
            {
                "company": item["company"],
                "title": item["position"],
                "dates": f'{item["duration"]["start"]} - {item["duration"]["end"]}',
                "location": item["location"],
                "bullets": item["achievements"],
            }
            for item in data["experience"]
        ],
        "education": [
            {
                "school": item["institution"],
                "degree": f'{item["degree"]} in {item["field"]}',
                "dates": f'{item["duration"]["start"]} - {item["duration"]["end"]}',
                "gpa": "",
                "details": [item["location"]],
            }
            for item in data["education"]
        ],
        "skills": {
            "technical": data["skills"]["technical"],
            "frameworks": ["FastAPI", "PyTorch", "scikit-learn"],
            "tools": ["Docker", "AWS", "CI/CD"],
            "soft": data["skills"]["soft"],
        },
        "projects": [
            {
                "title": item["name"],
                "description": " ".join(item["description"]),
                "tech_stack": [],
                "links": [
                    value
                    for key in ("github", "demo")
                    if (value := item.get(key))
                ],
            }
            for item in data["projects"]
        ],
        "certifications": [
            f'{item["name"]} | {item["issuer"]} | {item["dateObtained"]}'
            for item in data["certifications"]
        ],
        "raw_text": render_resume_text(data),
    }
    assert_synthetic_fixture_text(json.dumps(parsed, ensure_ascii=False))
    return parsed
