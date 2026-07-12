from __future__ import annotations

from io import BytesIO
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)

from .template_base import ResumeTemplate


def _safe_list(items: Any) -> List[str]:
    if not items:
        return []
    if isinstance(items, list):
        return [str(i) for i in items if i]
    return [str(items)]


def _safe_add_style(styles, style: ParagraphStyle):
    """Safely add or update a style in the stylesheet."""
    if style.name in styles.byName:
        # Style exists, update it
        existing = styles.byName[style.name]
        for attr in ['fontName', 'fontSize', 'alignment', 'textColor', 'leading', 
                     'leftIndent', 'bulletIndent', 'spaceAfter', 'spaceBefore']:
            if hasattr(style, attr):
                setattr(existing, attr, getattr(style, attr))
    else:
        # Style doesn't exist, add it
        styles.add(style)


class LaTeXModernTemplate(ResumeTemplate):
    """LaTeX-inspired modern template (tight spacing, two-column entries)."""

    template_id = "latex_modern"
    template_name = "LaTeX Modern"
    description = "LaTeX-inspired layout with crisp rules and two-column entries."

    def generate_pdf(self, tailored_data: Dict[str, Any]) -> bytes:
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        _safe_add_style(styles, ParagraphStyle(
            name="HeaderName",
            fontName="Times-Bold",
            fontSize=22,
            alignment=1,
            spaceAfter=4,
        ))
        _safe_add_style(styles, ParagraphStyle(
            name="HeaderInfo",
            fontName="Times-Roman",
            fontSize=10,
            alignment=1,
            spaceAfter=8,
        ))
        _safe_add_style(styles, ParagraphStyle(
            name="SectionTitle",
            fontName="Times-Bold",
            fontSize=12,
            spaceAfter=3,
            spaceBefore=6,
        ))
        _safe_add_style(styles, ParagraphStyle(
            name="Body",
            fontName="Times-Roman",
            fontSize=10,
            leading=12,
            spaceAfter=2,
        ))
        _safe_add_style(styles, ParagraphStyle(
            name="Bullet",
            fontName="Times-Roman",
            fontSize=10,
            leading=12,
            leftIndent=12,
            bulletIndent=0,
            spaceAfter=1,
        ))

        elements: List[Any] = []

        contact = tailored_data.get("contact", {}) or {}
        name = contact.get("name", "Candidate Name")
        
        # Target job title (professional checklist: headline matches JD)
        target_job_title = tailored_data.get("target_job_title") or tailored_data.get("targetJobTitle")
        
        # Format contact info cleanly (professional checklist: clean, easy to scan)
        contact_parts = []
        location_parts = [contact.get("city"), contact.get("country") or contact.get("state")]
        location = " | ".join([p for p in location_parts if p])
        if location:
            contact_parts.append(location)
        if contact.get("email"):
            contact_parts.append(contact.get("email"))
        if contact.get("phone"):
            contact_parts.append(contact.get("phone"))
        
        # Links on separate line or combined
        links = []
        if contact.get("github"):
            links.append(f"GitHub: {contact.get('github')}")
        if contact.get("linkedin"):
            links.append(f"LinkedIn: {contact.get('linkedin')}")
        if contact.get("website"):
            links.append(f"Portfolio: {contact.get('website')}")
        
        contact_line = " | ".join(contact_parts) if contact_parts else ""
        links_line = " | ".join(links) if links else ""

        # Name (large, centered for LaTeX style)
        elements.append(Paragraph(name, styles["HeaderName"]))
        
        # Target job title if provided (professional checklist requirement)
        if target_job_title:
            elements.append(Spacer(1, 2))
            elements.append(Paragraph(target_job_title, styles["HeaderInfo"]))
        
        # Contact info
        if contact_line:
            elements.append(Spacer(1, 2))
            elements.append(Paragraph(contact_line, styles["HeaderInfo"]))
        if links_line:
            elements.append(Paragraph(links_line, styles["HeaderInfo"]))
        
        # Add spacing after header (fixes overlapping)
        elements.append(Spacer(1, 8))

        def section(title: str):
            elements.append(Spacer(1, 4))
            elements.append(Paragraph(title, styles["SectionTitle"]))
            elements.append(HRFlowable(width="100%", color=colors.black, thickness=0.8))
            elements.append(Spacer(1, 3))

        # Summary (professional checklist: 2-4 lines, uses keywords, states impact)
        summary = tailored_data.get("summary")
        if summary:
            section("Professional Summary")
            # Split summary into sentences and limit to 2-4 lines for professional format
            summary_sentences = summary.split('. ')
            # Take first 2-3 sentences (typically 2-4 lines)
            summary_text = '. '.join(summary_sentences[:3]).strip()
            if not summary_text.endswith('.'):
                summary_text += '.'
            elements.append(Paragraph(summary_text, styles["Body"]))

        # Skills (professional checklist: grouped logically, only actual skills)
        skills = tailored_data.get("skills", {}) or {}
        skill_lines = []
        # Professional format: prioritize technical skills, group logically
        if skills.get("technical"):
            skill_lines.append(f"<b>Technical:</b> {', '.join(_safe_list(skills['technical']))}")
        if skills.get("languages"):
            skill_lines.append(f"<b>Languages:</b> {', '.join(_safe_list(skills['languages']))}")
        # Soft skills integrated into experience bullets per checklist, but include if provided
        if skills.get("soft") and len(skills.get("soft", [])) > 0:
            skill_lines.append(f"<b>Soft Skills:</b> {', '.join(_safe_list(skills['soft']))}")
        if skills.get("industry"):
            skill_lines.append(f"<b>Industry:</b> {', '.join(_safe_list(skills['industry']))}")
        if skill_lines:
            section("Technical Skills")
            for line in skill_lines:
                elements.append(Paragraph(line, styles["Body"]))

        # Competencies (optional)
        competencies = tailored_data.get("competencies") or tailored_data.get("coreCompetencies") or []
        if competencies:
            section("Core Competencies")
            for comp in competencies:
                elements.append(Paragraph(comp, styles["Bullet"], bulletText="•"))

        # Experience
        experiences = tailored_data.get("experience") or []
        if experiences:
            section("Professional Experience")
            for exp in experiences:
                title = exp.get("position", "Title")
                company = exp.get("company", "")
                location = exp.get("location", "")
                duration = exp.get("duration", {}) or {}
                start = duration.get("start", "")
                end = duration.get("end", "")
                date_str = " — ".join([s for s in [start, end] if s])
                left = ", ".join([p for p in [title, company, location] if p])

                header = [[Paragraph(left, styles["Body"]), Paragraph(date_str, styles["Body"])]]
                table = Table(header, colWidths=[doc.width * 0.65, doc.width * 0.35], hAlign="LEFT")
                table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ]
                    )
                )
                elements.append(table)

                achievements = _safe_list(exp.get("achievements"))
                desc = exp.get("description")
                if desc:
                    achievements = [desc] + achievements
                for ach in achievements:
                    elements.append(Paragraph(ach, styles["Bullet"], bulletText="•"))
                elements.append(Spacer(1, 3))

        # Projects
        projects = tailored_data.get("projects") or tailored_data.get("featuredProjects") or []
        if projects:
            section("Featured Projects")
            for proj in projects:
                title = proj.get("name", "Project")
                links = []
                if proj.get("github"):
                    links.append(proj["github"])
                if proj.get("demo"):
                    links.append(proj["demo"])
                link_line = " | ".join(links)
                elements.append(
                    Paragraph(
                        f"<b>{title}</b>" + (f" — {link_line}" if link_line else ""),
                        styles["Body"],
                    )
                )
                highlights = _safe_list(proj.get("highlights") or proj.get("description"))
                for hl in highlights:
                    elements.append(Paragraph(hl, styles["Bullet"], bulletText="•"))
                elements.append(Spacer(1, 3))

        # Education
        education = tailored_data.get("education") or []
        if education:
            section("Education")
            for edu in education:
                degree = edu.get("degree", "")
                field = edu.get("field", "")
                school = edu.get("institution", "")
                location = edu.get("location", "")
                duration = edu.get("duration", {}) or {}
                date_str = " — ".join([s for s in [duration.get("start"), duration.get("end")] if s])
                left = ", ".join([p for p in [degree, field, school, location] if p])
                header = [[Paragraph(left, styles["Body"]), Paragraph(date_str, styles["Body"])]]
                table = Table(header, colWidths=[doc.width * 0.65, doc.width * 0.35], hAlign="LEFT")
                table.setStyle(
                    TableStyle(
                        [
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ]
                    )
                )
                elements.append(table)
                honors = _safe_list(edu.get("honors"))
                for h in honors:
                    elements.append(Paragraph(h, styles["Bullet"], bulletText="•"))
                elements.append(Spacer(1, 3))

        # Certifications
        certs = tailored_data.get("certifications") or []
        if certs:
            section("Certifications & Open Source")
            for cert in certs:
                parts = [
                    cert.get("name"),
                    cert.get("issuer"),
                    cert.get("dateObtained"),
                ]
                elements.append(Paragraph(" | ".join([p for p in parts if p]), styles["Body"]))

        doc.build(elements)
        return buf.getvalue()

