"""
All prompt templates for the Career Readiness Engine.
Centralised here so agents stay clean and prompts are easy to iterate.
"""

AUDIT_PROMPT = """
You are reviewing a student's resume against {jd_count} real job descriptions.

<RESUME>
{resume_text}
</RESUME>

<JOB_DESCRIPTIONS>
{all_jds_concatenated}
</JOB_DESCRIPTIONS>

<MARKET_SIGNAL>
{perplexity_output}
</MARKET_SIGNAL>

For each requirement mentioned in 50%+ of JDs:
- Check if resume shows real evidence (not just keyword mention)
- Flag claims the student may struggle to defend in an interview

Return ONLY valid JSON:
{{
  "gaps": [{{"skill": str, "jd_frequency": int, "resume_evidence": str|null}}],
  "undefendable_claims": [{{"bullet": str, "reason": str}}],
  "strengths": [{{"skill": str, "evidence": str}}],
  "percentile_estimate": int,
  "gap_type": "skills" | "framing" | "ready"
}}
"""

VERDICT_PROMPT = """
Convert this audit JSON into 2-3 paragraphs of honest career advice.
Tone: mentor who respects the person enough to tell the truth.
No fluff. No 'great job!' Be specific — name actual gaps and strengths.
If ready: say so, name which companies to hit first.
If not ready: give the exact exit condition.

{audit_json}
"""

REFRAME_PROMPT = """
You are a resume writing expert. The following bullet point from a resume
was flagged as "undefendable" — the candidate would struggle to back it up
in an interview with specific examples or metrics.

Original bullet: {original_bullet}
Reason it's weak: {reason}
Candidate's actual skills: {skills}
Target role: {target_role}

Rewrite this bullet to be:
1. Honest — only claims what the evidence supports
2. Specific — uses numbers, tools, or outcomes where possible
3. Interview-ready — the candidate can explain every word

Return JSON:
{{
  "original": str,
  "rewritten": str,
  "why_better": str
}}
"""

LEARNING_MODULE_PROMPT = """
Create a focused 14-day learning module for a career-switcher.

Gap skill: {gap_skill}
Target role: {target_role}
Current level: {current_level}
Available project ideas: {project_ideas}
Available resources: {resources}

Design a daily plan where:
- Days 1-3: Core concept learning (theory + tutorials)
- Days 4-7: Build the project (hands-on)
- Days 8-10: Polish + deploy the project
- Days 11-12: Practice explaining it (interview prep)
- Days 13-14: Buffer + review

Return JSON:
{{
  "module_title": str,
  "gap_skill": str,
  "project": {{
    "title": str,
    "description": str,
    "tech_stack": [str],
    "github_ready": bool
  }},
  "resources": [
    {{"title": str, "url": str, "type": "video"|"article"|"course", "day": int}}
  ],
  "daily_plan": [
    {{"day": int, "focus": str, "tasks": [str], "hours": float}}
  ],
  "exit_condition": str
}}
"""

APPLY_NOW_PROMPT = """
The candidate is ready to apply. Based on these audit results,
generate a prioritised list of companies to target.

Audit results: {audit_json}
Top matching companies: {companies}
Resume strengths: {strengths}

For each company, provide:
1. Why this company is a good match
2. The specific angle to lead with (based on resume strengths)
3. A one-line email hook

Return JSON:
{{
  "companies": [
    {{
      "name": str,
      "match_reason": str,
      "angle": str,
      "email_hook": str,
      "priority": int
    }}
  ]
}}
"""
