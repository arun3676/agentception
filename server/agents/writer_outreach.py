from __future__ import annotations
import os, textwrap, random
from typing import List, Dict, Any, Callable, Awaitable
import httpx
import re

DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")

TEMPLATE = textwrap.dedent("""\
    System: You are an expert copywriter specializing in personalized, professional outreach for top-tier tech talent.
    Your task is to write a short, sharp, and compelling outreach email.

    **CRITICAL CONSTRAINTS:**
    1.  **Word Count:** The email BODY must be under 120 words. Be concise.
    2.  **Tone:** Professional, direct, and slightly informal. Confident but not arrogant.
    3.  **Format:** Return ONLY the subject and body, exactly as specified below. No extra text or markdown.
        SUBJECT: <subject line>
        BODY:
        <email body>

    **INPUT CONTEXT:**
    -   **TARGET ROLE:** {role}
    -   **MY KEY SKILLS (Value Props):** {value_props}
    -   **MY PROOF POINTS (Experience):** {proofs}
    -   **MY RESUME SNIPPET:** {resume_snip}

    -   **TARGET COMPANY:** {name}
    -   **COMPANY WEBSITE:** {homepage}
    -   **COMPANY DESCRIPTION:** {blurb}
    -   **RELEVANT JOB POSTING:**
        - Title: {job_title}
        - URL: {job_url}
        - Snippet: {job_snippet}
    -   **COMPANY-SPECIFIC INTELLIGENCE (USE THIS!):**
        {intel_context}

    **INSTRUCTIONS:**
    1.  **Subject Line:** Create a concise subject line (max 12 words). It MUST reference the specific job title. Example: "Regarding the AI Engineer Position".
    2.  **Email Body:**
        a. **Opening Hook (1 sentence):** Start by stating you saw the specific job posting. Reference something from the job snippet or the company's tech.
        b. **Value Proposition (1-2 sentences):** Connect your skills/proof points directly to the requirements mentioned in the job snippet. Show a clear, direct match.
        c. **Call to Action (1 sentence):** End with a clear, low-friction ask for a brief chat about this role.
    
    **EXAMPLE OUTPUT:**
    SUBJECT: Inquiry for the Senior AI Engineer role
    BODY:
    I came across your posting for the Senior AI Engineer role and was particularly interested in the focus on scalable RAG systems. This is a direct match for my expertise, having shipped production RAG systems with reranking and evals.

    My experience in agentic observability could help with the telemetry challenges you mentioned for this position.

    Are you available for a brief chat next week to discuss this opportunity?
    ---
    """)


def _format_intel(company: Dict[str, Any]) -> str:
    """Formats the enhanced research intelligence into a string for the prompt."""
    intel = company.get("intel", {})
    if not intel:
        return "No specific intelligence gathered. Rely on the company description."

    lines = []
    if intel.get("recent_news"):
        lines.append(f"- Technical News/Blog: {intel['recent_news']}")
    if intel.get("tech_stack"):
        lines.append(f"- Tech Stack: {intel['tech_stack']}")
    if intel.get("funding"):
        lines.append(f"- Funding: {intel['funding']}")
    if intel.get("competitors"):
        lines.append(f"- Competitors: {', '.join(intel['competitors'])}")

    return "\n".join(lines)


async def write_emails(ragdoc: Dict[str, Any], n: int = 5, emit: Callable[[Any], Awaitable[None]] | None = None) -> List[Dict[str,str]]:
    """
    Generate targeted outreach emails using compact context and small model
    
    Args:
        ragdoc: RAG document with companies, role profile, resume
        n: Number of emails to generate
        emit: Optional function to emit timeline events
        
    Returns:
        List of email dictionaries with company, subject, body, mailto
    """
    if emit:
        await emit(f"📧 Generating {n} outreach emails for run {ragdoc.get('run_id', 'unknown')}")
    
    role = ragdoc["role"]; prof = ragdoc["role_profile"]; city = ragdoc["city"]
    vprops = ", ".join(prof.get("value_props", []))
    proofs = ", ".join(prof.get("proofs", []))
    picks = [c for c in ragdoc["companies"] if c.get("name") and c.get("job_posting")][:n]
    out = []

    for i, c in enumerate(picks):
        if emit:
            await emit(f"Drafting email {i+1}/{len(picks)} for {c['name']}...")

        intel_context = _format_intel(c)
        job_posting = c.get("job_posting", {})
        prompt = TEMPLATE.format(
            role=role, 
            value_props=vprops,
            proofs=proofs,
            name=c["name"], 
            blurb=(c.get("blurb") or "")[:240],
            homepage=c.get("homepage") or c["source_url"], 
            city=city,
            resume_snip=(ragdoc.get("resume_excerpt") or "Not provided")[:400],
            job_title=job_posting.get("title", role),
            job_url=job_posting.get("url", c.get("homepage")),
            job_snippet=job_posting.get("snippet", "N/A"),
            intel_context=intel_context
        )
        
        # Fallback in case LLM fails
        subj, body = f"{role} at {c['name']}", f"Hi {c['name']} team, I'm interested in the {role} role."

        try:
            if not DEEPSEEK_KEY:
                raise ValueError("DEEPSEEK_API_KEY not set")
            async with httpx.AsyncClient(timeout=40) as client:
                r = await client.post("https://api.deepseek.com/chat/completions",
                    headers={"Authorization": f"Bearer {DEEPSEEK_KEY}","Content-Type":"application/json"},
                    json={
                        "model": "deepseek-chat", 
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.5,
                        "max_tokens": 400
                    })
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]

            # Robustly parse SUBJECT and BODY
            subj_match = re.search(r"SUBJECT:\s*(.*)", text)
            body_match = re.search(r"BODY:\s*([\s\S]*)", text)
            subj = subj_match.group(1).strip() if subj_match else f"{role} at {c['name']}"
            body = body_match.group(1).strip() if body_match else text.strip()

        except Exception as e:
            if emit:
                await emit(f"⚠️ LLM failed for {c['name']}: {e}. Using fallback.")
            print(f"❌ LLM generation failed for {c['name']}: {e}")

        job_url = job_posting.get("url") or c.get("homepage") or c.get("source_url")
        if job_url and "Apply here:" not in body:
            body = f"{body}\n\nApply here: {job_url}".strip()

        out.append({
            "company": c["name"],
            "subject": subj,
            "body": body,
            "mailto": c.get("contact_hint"),
            "job_url": job_url
        })

    if emit:
        await emit(f"✅ Generated {len(out)} personalized emails.")
    return out