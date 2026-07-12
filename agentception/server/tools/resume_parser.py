from __future__ import annotations
import re
from typing import Dict, List, Any, Optional

# Header keyword -> section name. First match wins, so order matters.
# 'other' sections are never extracted; they exist only to end the section before
# them (an 'OPEN SOURCE' header would otherwise let experience swallow it).
#
# This list is deliberately explicit rather than "treat every detected header as a
# boundary": the `is_header` test below also fires on ALL-CAPS and Title-Case
# *content* — project titles like 'LLM CODE ANALYZER' — so generalizing it
# truncates the projects section. Verified against real resumes.
_SECTION_KEYWORDS = (
    ('summary', ('summary', 'objective', 'overview', 'profile')),
    ('experience', ('experience', 'work', 'employment', 'career', 'work history')),
    ('education', ('education', 'academic', 'degree', 'university', 'college')),
    ('skills', ('skills', 'technologies', 'tech stack', 'proficiencies', 'expertise')),
    ('projects', ('projects', 'portfolio')),
    ('certifications', ('certifications', 'certificates', 'awards', 'publications')),
    ('other', ('open source', 'contribution', 'volunteer', 'leadership',
               'activities', 'interests', 'languages', 'references',
               'patents', 'speaking', 'community')),
)


def _classify_header(line: str) -> Optional[str]:
    """Map a header line to its section, or None when it isn't a known header."""
    lower = line.lower()
    for section, keywords in _SECTION_KEYWORDS:
        if any(kw in lower for kw in keywords):
            return section
    return None


def parse_resume_structured(text: str) -> Dict[str, Any]:
    """
    Parse raw resume text into structured fields.
    Returns a dict with contact, summary, experience, education, skills, projects, certifications.
    """
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    result = {
        "contact": {
            "name": "",
            "email": "",
            "phone": "",
            "location": "",
            "linkedin": "",
            "github": "",
            "portfolio": "",
        },
        "summary": "",
        "experience": [],
        "education": [],
        "skills": {
            "technical": [],
            "frameworks": [],
            "tools": [],
            "soft": [],
        },
        "projects": [],
        "certifications": [],
        "raw_text": text,
    }
    
    # Extract contact info from first 15 lines
    contact_text = ' '.join(lines[:15])
    
    # Name: usually first non-empty line, 2-3 words, Title Case
    for line in lines[:5]:
        if 2 <= len(line.split()) <= 4 and line.istitle() and not any(kw in line.lower() for kw in ['resume', 'cv', 'curriculum', 'vitae']):
            result["contact"]["name"] = line
            break
    if not result["contact"]["name"]:
        result["contact"]["name"] = lines[0] if lines else ""
    
    # Email
    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', contact_text)
    if email_match:
        result["contact"]["email"] = email_match.group(0)
    
    # Phone
    phone_match = re.search(r'[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}', contact_text)
    if phone_match:
        result["contact"]["phone"] = phone_match.group(0)
    
    # LinkedIn
    li_match = re.search(r'linkedin\.com/in/[\w-]+', text, re.IGNORECASE)
    if li_match:
        result["contact"]["linkedin"] = "https://" + li_match.group(0)
    
    # GitHub
    gh_match = re.search(r'github\.com/[\w-]+', text, re.IGNORECASE)
    if gh_match:
        result["contact"]["github"] = "https://" + gh_match.group(0)
    
    # Portfolio / personal website
    portfolio_match = re.search(r'(?:(?:https?://)?)([\w-]+\.(?:com|io|dev|net|org)[/\w-]*)', text, re.IGNORECASE)
    if portfolio_match:
        url = portfolio_match.group(0)
        if 'linkedin' not in url.lower() and 'github' not in url.lower():
            result["contact"]["portfolio"] = url if url.startswith('http') else 'https://' + url
    
    # Location
    location_patterns = [
        r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*(?:[A-Z]{2}|USA?|United\sStates))',
        r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*[A-Z][a-z]+)',
    ]
    for pattern in location_patterns:
        loc_match = re.search(pattern, contact_text)
        if loc_match:
            result["contact"]["location"] = loc_match.group(1)
            break
    
    # Identify sections
    section_map = {}
    for i, line in enumerate(lines):
        # Section headers are usually short, all caps, or end with colon
        is_header = (
            len(line) < 40 and
            (line.isupper() or 
             line.endswith(':') or
             re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$', line) or
             re.match(r'^={3,}$', line) or
             re.match(r'^-{3,}$', line))
        )
        
        if is_header:
            # Known headers are named so they can be extracted; unrecognised ones
            # ('OPEN SOURCE', 'PATENTS', 'SPEAKING'...) still end the previous
            # section rather than bleeding into it.
            section = _classify_header(line)
            if section:
                section_map[i] = section

    # Parse summary
    summary_indices = [i for i, sec in section_map.items() if sec == 'summary']
    if summary_indices:
        start = summary_indices[0] + 1
        end = min([i for i in section_map if i > start], default=min(start + 10, len(lines)))
        result["summary"] = ' '.join(lines[start:end]).strip()
    
    # Parse experience
    exp_indices = [i for i, sec in section_map.items() if sec == 'experience']
    if exp_indices:
        start = exp_indices[0] + 1
        end = min([i for i in section_map if i > start], default=len(lines))
        exp_lines = lines[start:end]
        result["experience"] = _parse_experience_entries(exp_lines)
    
    # Parse education
    edu_indices = [i for i, sec in section_map.items() if sec == 'education']
    if edu_indices:
        start = edu_indices[0] + 1
        end = min([i for i in section_map if i > start], default=len(lines))
        edu_lines = lines[start:end]
        result["education"] = _parse_education_entries(edu_lines)
    
    # Parse skills
    skill_indices = [i for i, sec in section_map.items() if sec == 'skills']
    if skill_indices:
        start = skill_indices[0] + 1
        end = min([i for i in section_map if i > start], default=min(start + 5, len(lines)))
        skill_text = ' '.join(lines[start:end])
        result["skills"] = _parse_skills(skill_text)
    
    # Parse projects
    proj_indices = [i for i, sec in section_map.items() if sec == 'projects']
    if proj_indices:
        start = proj_indices[0] + 1
        end = min([i for i in section_map if i > start], default=len(lines))
        proj_lines = lines[start:end]
        result["projects"] = _parse_project_entries(proj_lines)
    
    # Parse certifications
    cert_indices = [i for i, sec in section_map.items() if sec == 'certifications']
    if cert_indices:
        start = cert_indices[0] + 1
        end = min([i for i in section_map if i > start], default=min(start + 5, len(lines)))
        cert_lines = lines[start:end]
        result["certifications"] = [l.strip('-• ') for l in cert_lines if l.strip() and not l.startswith('=') and not l.startswith('-')]
    
    return result


def _parse_experience_entries(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse experience section into structured entries."""
    entries = []
    current = None
    
    for line in lines:
        # Date pattern often signals a new entry
        date_match = re.search(r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})\s*[-–—]\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4}|Present|Current)', line, re.IGNORECASE)
        
        # Or company + title on same line
        company_title_match = re.match(r'^([A-Z][^,]+)[,\s]+([A-Z][^,]+)$', line)
        
        is_new_entry = (
            date_match or
            (company_title_match and len(line) < 80) or
            re.match(r'^[A-Z][a-zA-Z\s&]+(?:Inc\.?|LLC|Ltd\.?|Corp\.?|Company|Technologies|Solutions|Group)$', line)
        )
        
        if is_new_entry and not line.startswith('•') and not line.startswith('-'):
            if current:
                entries.append(current)
            current = {
                "company": "",
                "title": "",
                "dates": "",
                "location": "",
                "bullets": [],
            }
            
            if date_match:
                current["dates"] = date_match.group(0)
                # Remove date from line to get company/title
                clean_line = line[:date_match.start()].strip() + line[date_match.end():].strip()
                if clean_line:
                    parts = [p.strip() for p in re.split(r'[,|]', clean_line) if p.strip()]
                    if len(parts) >= 2:
                        current["company"] = parts[0]
                        current["title"] = parts[1]
                    elif parts:
                        current["company"] = parts[0]
            else:
                if company_title_match:
                    current["company"] = company_title_match.group(1).strip()
                    current["title"] = company_title_match.group(2).strip()
                else:
                    current["company"] = line.strip()
        elif current and (line.startswith('•') or line.startswith('-') or line.startswith('*')):
            current["bullets"].append(line.strip('•- ').strip())
        elif current and len(line) < 50 and not line.startswith('•'):
            # Could be title or location
            if not current["title"]:
                current["title"] = line
            elif not current["location"]:
                current["location"] = line
        elif current:
            current["bullets"].append(line)
    
    if current:
        entries.append(current)

    return [_fix_role_company_order(e) for e in entries]


_ROLE_WORDS = re.compile(
    r'\b(engineer|developer|manager|analyst|scientist|intern|consultant|designer|'
    r'architect|researcher|specialist|lead|director|administrator|head|founder|'
    r'president|vp|owner|principal|staff|chief|officer|associate|technician)\b',
    re.IGNORECASE,
)


def _fix_role_company_order(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Resumes list role and employer in either order. If the company field holds
    a job title and the title field doesn't, swap them."""
    company, title = entry.get("company", ""), entry.get("title", "")
    if company and _ROLE_WORDS.search(company) and not _ROLE_WORDS.search(title or ""):
        entry["company"], entry["title"] = title, company
    return entry


def _parse_education_entries(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse education section into structured entries."""
    entries = []
    current = None
    
    for line in lines:
        # New entry usually has degree or school name
        is_new_entry = (
            re.search(r'\b(?:B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|Ph\.?D\.?|MBA|Bachelor|Master|Doctorate|Associate)\b', line, re.IGNORECASE) or
            re.search(r'\b(?:University|College|Institute|School)\b', line, re.IGNORECASE)
        )
        
        if is_new_entry and not line.startswith('•') and not line.startswith('-'):
            if current:
                entries.append(current)
            current = {
                "school": "",
                "degree": "",
                "dates": "",
                "gpa": "",
                "details": [],
            }
            
            # Try to extract degree and school
            degree_match = re.search(r'((?:B\.?S\.?|M\.?S\.?|B\.?A\.?|M\.?A\.?|Ph\.?D\.?|MBA|Bachelor|Master|Doctorate|Associate)[^,]*)', line, re.IGNORECASE)
            school_match = re.search(r'((?:University|College|Institute|School)[^,]*)', line, re.IGNORECASE)
            
            if degree_match:
                current["degree"] = degree_match.group(1).strip()
            if school_match:
                current["school"] = school_match.group(1).strip()
            
            # If we couldn't parse, use the whole line
            if not current["school"] and not current["degree"]:
                if 'University' in line or 'College' in line:
                    current["school"] = line.strip()
                else:
                    current["degree"] = line.strip()
        elif current and (line.startswith('•') or line.startswith('-')):
            current["details"].append(line.strip('•- ').strip())
        elif current:
            # Try to extract GPA or dates
            gpa_match = re.search(r'GPA[:\s]+([\d\.]+)', line, re.IGNORECASE)
            if gpa_match:
                current["gpa"] = gpa_match.group(1)
            date_match = re.search(r'(\d{4})\s*[-–—]\s*(\d{4}|Present)', line, re.IGNORECASE)
            if date_match:
                current["dates"] = date_match.group(0)
            elif len(line) < 60:
                current["details"].append(line)
    
    if current:
        entries.append(current)
    
    return entries


def _parse_skills(text: str) -> Dict[str, List[str]]:
    """Parse skills text into categorized skills."""
    # Common skills
    tech_skills = [
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "kotlin", "swift",
        "ruby", "php", "scala", "r", "matlab", "sql", "html", "css", "dart", "bash", "shell",
    ]
    frameworks = [
        "react", "vue", "angular", "node.js", "django", "flask", "fastapi", "spring", "express",
        "next.js", "nuxt", "svelte", "laravel", "rails", "asp.net", "tensorflow", "pytorch",
        "keras", "scikit-learn", "pandas", "numpy", "matplotlib", "jupyter", "opencv",
    ]
    tools = [
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins", "git", "github",
        "gitlab", "ci/cd", "ansible", "prometheus", "grafana", "elasticsearch", "kafka",
        "postgresql", "mysql", "mongodb", "redis", "cassandra", "dynamodb", "serverless", "lambda",
        "nginx", "apache", "linux", "unix", "windows", "macos", "jupyter", "colab",
    ]
    soft = [
        "leadership", "mentoring", "communication", "stakeholder management", "collaboration",
        "teamwork", "ownership", "product thinking", "prioritization", "problem solving",
        "cross-functional", "agile", "scrum", "time management", "critical thinking",
    ]
    
    text_lower = text.lower()
    
    # Split by common delimiters
    all_items = re.split(r'[,;|•\-\n]', text)
    all_items = [s.strip() for s in all_items if s.strip() and len(s.strip()) > 1]
    
    result = {
        "technical": [],
        "frameworks": [],
        "tools": [],
        "soft": [],
    }
    
    for item in all_items:
        # Drop category labels like "AI/ML Frameworks & Tools: LangChain" -> "LangChain"
        item = re.sub(r'^[A-Za-z &/]{3,40}:\s*', '', item).strip()
        if not item:
            continue
        item_lower = item.lower()
        matched = False
        
        for skill in tech_skills:
            if skill in item_lower:
                result["technical"].append(item.title() if item.islower() else item)
                matched = True
                break
        
        if not matched:
            for skill in frameworks:
                if skill in item_lower:
                    result["frameworks"].append(item.title() if item.islower() else item)
                    matched = True
                    break
        
        if not matched:
            for skill in tools:
                if skill in item_lower:
                    result["tools"].append(item.title() if item.islower() else item)
                    matched = True
                    break
        
        if not matched:
            for skill in soft:
                if skill in item_lower:
                    result["soft"].append(item.title() if item.islower() else item)
                    matched = True
                    break
        
        if not matched and len(item) > 2:
            # Check if it looks like a skill (no spaces or short)
            if len(item.split()) <= 3:
                result["technical"].append(item.title() if item.islower() else item)
    
    # Deduplicate
    for key in result:
        seen = set()
        unique = []
        for skill in result[key]:
            if skill.lower() not in seen:
                seen.add(skill.lower())
                unique.append(skill)
        result[key] = unique
    
    return result


def _parse_project_entries(lines: List[str]) -> List[Dict[str, Any]]:
    """Parse project section into structured entries."""
    entries = []
    current = None
    
    for line in lines:
        # New project usually starts with a title (not a bullet)
        if not line.startswith('•') and not line.startswith('-') and len(line) < 80 and len(line) > 5:
            if current:
                entries.append(current)
            current = {
                "title": line.strip(),
                "description": "",
                "tech_stack": [],
                "links": [],
            }
        elif current and (line.startswith('•') or line.startswith('-')):
            content = line.strip('•- ').strip()
            # Check for tech stack mention
            if 'tech' in content.lower() or 'stack' in content.lower() or 'built with' in content.lower():
                tech_match = re.search(r':\s*(.+)', content)
                if tech_match:
                    current["tech_stack"] = [t.strip() for t in tech_match.group(1).split(',')]
                else:
                    current["description"] += ' ' + content
            else:
                current["description"] += ' ' + content
        elif current:
            current["description"] += ' ' + line
    
    if current:
        entries.append(current)
    
    # Clean up descriptions
    for entry in entries:
        entry["description"] = entry["description"].strip()
    
    return entries
