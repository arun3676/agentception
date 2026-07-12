"""Resume parsing: the Reducto markdown adapter and the structured parser.

These lock in bug fixes that are otherwise easy to regress silently:
- Reducto emits markdown, which the section parser can't read as-is
- page-continuation banners used to parse as job entries
- skills lines carry a category label that used to be kept as part of the skill
- role and employer appear in either order on the page
"""

from server.tools.reducto_parser import markdown_to_plain_text
from server.tools.resume_parser import (
    _classify_header,
    _fix_role_company_order,
    _parse_skills,
    parse_resume_structured,
)


class TestMarkdownToPlainText:
    def test_h1_keeps_case_so_name_detection_works(self):
        assert markdown_to_plain_text("# Arun Kumar Chukkala").strip() == "Arun Kumar Chukkala"

    def test_subheadings_are_uppercased_for_section_detection(self):
        assert "PROFESSIONAL SUMMARY" in markdown_to_plain_text("## Professional Summary")

    def test_page_continuation_banner_is_dropped(self):
        md = "# Arun Kumar\n\nArun Kumar Chukkala (cont.)\n\nreal content"
        out = markdown_to_plain_text(md)
        assert "cont." not in out
        assert "real content" in out

    def test_continued_spelled_out_is_also_dropped(self):
        assert "Jane Doe" not in markdown_to_plain_text("Jane Doe (continued)")

    def test_inline_html_from_reducto_is_stripped(self):
        assert markdown_to_plain_text("<b>Associate</b> Engineer") == "Associate Engineer"

    def test_bullets_become_the_prefix_the_entry_parser_expects(self):
        assert markdown_to_plain_text("- shipped a thing").startswith("•")

    def test_profile_urls_survive(self):
        out = markdown_to_plain_text("[GitHub](https://github.com/arun)")
        assert "https://github.com/arun" in out


class TestClassifyHeader:
    def test_known_sections_map_to_their_name(self):
        assert _classify_header("PROFESSIONAL SUMMARY") == "summary"
        assert _classify_header("PROFESSIONAL EXPERIENCE") == "experience"
        assert _classify_header("EDUCATION") == "education"
        assert _classify_header("TECHNICAL SKILLS") == "skills"
        assert _classify_header("FEATURED PROJECTS") == "projects"
        assert _classify_header("CERTIFICATIONS") == "certifications"

    def test_boundary_only_sections_are_other(self):
        assert _classify_header("OPEN SOURCE CONTRIBUTIONS") == "other"
        assert _classify_header("LANGUAGES") == "other"
        assert _classify_header("REFERENCES") == "other"

    def test_work_keyword_wins_over_volunteer(self):
        # Known collision: 'work' maps to experience and is matched first, so a
        # "VOLUNTEER WORK" section is read as a job. Narrowing 'work' would break
        # "WORK HISTORY" / "WORK EXPERIENCE", so this is documented, not fixed.
        assert _classify_header("VOLUNTEER WORK") == "experience"
        assert _classify_header("VOLUNTEERING") == "other"

    def test_all_caps_content_is_not_a_header(self):
        # Project titles are ALL CAPS in real resumes; treating them as section
        # boundaries truncates the projects section.
        assert _classify_header("LLM CODE ANALYZER") is None
        assert _classify_header("JOB SEARCH ASSISTANT") is None


class TestParseSkills:
    def test_category_label_is_stripped_from_the_first_skill(self):
        buckets = _parse_skills("Programming & Development: Python, TypeScript, React")
        flat = [s for bucket in buckets.values() for s in bucket]
        assert "Python" in flat
        assert not any(s.startswith("Programming") for s in flat)

    def test_plain_comma_list_still_parses(self):
        buckets = _parse_skills("Python, Docker, React")
        flat = [s for bucket in buckets.values() for s in bucket]
        assert {"Python", "Docker", "React"} <= set(flat)


class TestRoleCompanyOrder:
    def test_swaps_when_company_field_holds_the_job_title(self):
        entry = {"company": "Senior AI Engineer", "title": "Jefferies Group"}
        assert _fix_role_company_order(entry) == {
            "company": "Jefferies Group",
            "title": "Senior AI Engineer",
        }

    def test_leaves_correct_entries_alone(self):
        entry = {"company": "Jefferies Group", "title": "Senior AI Engineer"}
        assert _fix_role_company_order(dict(entry)) == entry

    def test_no_swap_when_both_look_like_roles(self):
        entry = {"company": "Engineer Inc", "title": "Staff Engineer"}
        assert _fix_role_company_order(dict(entry)) == entry


class TestParseResumeStructured:
    RESUME = "\n".join([
        "Jane Doe",
        "jane@example.com | +1 (415) 555-1234",
        "PROFESSIONAL SUMMARY",
        "Backend engineer with 5 years of experience.",
        "TECHNICAL SKILLS",
        "Languages: Python, TypeScript",
        "PROFESSIONAL EXPERIENCE",
        "Senior Backend Engineer | Jan 2021 - Present",
        "Acme Corp",
        "• Built a thing",
        "OPEN SOURCE CONTRIBUTIONS",
        "Maintainer of something",
    ])

    def test_extracts_contact(self):
        result = parse_resume_structured(self.RESUME)
        assert result["contact"]["name"] == "Jane Doe"
        assert result["contact"]["email"] == "jane@example.com"

    def test_open_source_header_stops_experience_bleeding(self):
        result = parse_resume_structured(self.RESUME)
        companies = " ".join(e["company"] for e in result["experience"])
        assert "Maintainer" not in companies

    def test_summary_is_captured(self):
        assert "Backend engineer" in parse_resume_structured(self.RESUME)["summary"]
