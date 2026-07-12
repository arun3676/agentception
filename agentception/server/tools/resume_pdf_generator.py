from __future__ import annotations

from typing import Any, Dict, List

from ..templates.resume_templates.classic_serif import ClassicSerifTemplate
from ..templates.resume_templates.latex_modern import LaTeXModernTemplate
from ..templates.resume_templates.modern_minimal import ModernMinimalTemplate
from ..templates.resume_templates.template_base import ResumeTemplate


_TEMPLATES: Dict[str, ResumeTemplate] = {
    "classic_serif": ClassicSerifTemplate(),
    "latex_modern": LaTeXModernTemplate(),
    "modern_minimal": ModernMinimalTemplate(),
}


def get_template(template_id: str) -> ResumeTemplate:
    """Return a template by id (defaults to classic_serif)."""
    return _TEMPLATES.get(template_id) or _TEMPLATES["classic_serif"]


def get_available_templates() -> List[Dict[str, str]]:
    """Return metadata for all templates."""
    return [
        {
            "id": tmpl.template_id,
            "name": tmpl.template_name,
            "description": tmpl.description,
        }
        for tmpl in _TEMPLATES.values()
    ]


def generate_pdf_from_template(tailored_data: Dict[str, Any], template_id: str = "classic_serif") -> bytes:
    """Generate a PDF using the selected template."""
    template = get_template(template_id)
    return template.generate_pdf(tailored_data)

