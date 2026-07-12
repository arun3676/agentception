from __future__ import annotations
import os, uuid, re
from collections import OrderedDict
from typing import Optional, Dict, List, Any

# Every upload mints a new token, so these would grow for the life of the process.
# Bounded LRU: the oldest resume is evicted once the cap is reached.
MAX_CACHED_RESUMES = int(os.getenv("MAX_CACHED_RESUMES", "200"))

# In-memory cache for resume text
_CACHE: "OrderedDict[str, str]" = OrderedDict()

# In-memory cache for resume insights
_INSIGHTS_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

# In-memory cache for structured resume profiles (parsed sections)
_PROFILE_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()


def _remember(cache: "OrderedDict[str, Any]", key: str, value: Any) -> None:
    """Insert into a bounded LRU cache, evicting the least recently used entry."""
    if key in cache:
        cache.move_to_end(key)
    cache[key] = value
    while len(cache) > MAX_CACHED_RESUMES:
        evicted, _ = cache.popitem(last=False)
        # Drop the whole resume together so the caches never disagree
        _INSIGHTS_CACHE.pop(evicted, None)
        _PROFILE_CACHE.pop(evicted, None)
        _CACHE.pop(evicted, None)

# Create uploads directory
UP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads"))
os.makedirs(UP, exist_ok=True)

# Common tech skills keywords for extraction
TECH_SKILLS_KEYWORDS = [
    # Languages
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "kotlin", "swift",
    "ruby", "php", "scala", "r", "matlab", "sql", "html", "css", "dart",
    # Frameworks & Libraries
    "react", "vue", "angular", "node.js", "django", "flask", "fastapi", "spring", "express",
    "next.js", "nuxt", "svelte", "laravel", "rails", "asp.net", "tensorflow", "pytorch",
    # Tools & Platforms
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins", "git", "github",
    "gitlab", "ci/cd", "ansible", "prometheus", "grafana", "elasticsearch", "kafka",
    # Databases
    "postgresql", "mysql", "mongodb", "redis", "cassandra", "dynamodb", "elasticsearch",
    # AI/ML
    "machine learning", "deep learning", "neural networks", "nlp", "computer vision",
    "llm", "gpt", "transformer", "bert", "rag", "vector database",
    # Other
    "microservices", "rest api", "graphql", "websocket", "grpc", "serverless", "lambda"
]

# Buckets for categorized skill extraction
SKILL_BUCKETS = {
    "technical": [
        # Core engineering
        "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust", "kotlin", "swift",
        "ruby", "php", "scala", "r", "matlab", "sql", "html", "css", "dart",
        "microservices", "rest api", "graphql", "grpc",
    ],
    "frameworks": [
        "react", "vue", "angular", "node.js", "django", "flask", "fastapi", "spring", "express",
        "next.js", "nuxt", "svelte", "laravel", "rails", "asp.net", "tensorflow", "pytorch",
    ],
    "tools": [
        "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "jenkins", "git", "github",
        "gitlab", "ci/cd", "ansible", "prometheus", "grafana", "elasticsearch", "kafka",
        "postgresql", "mysql", "mongodb", "redis", "cassandra", "dynamodb",
        "serverless", "lambda"
    ],
    "soft": [
        "leadership", "mentoring", "communication", "stakeholder management",
        "collaboration", "teamwork", "ownership", "product thinking", "prioritization",
        "problem solving", "cross-functional"
    ],
}

# Domain keywords to infer industry focus
DOMAIN_KEYWORDS = {
    "fintech": ["fintech", "financial", "banking", "payments", "trading", "wealth", "quant"],
    "healthcare": ["healthcare", "medtech", "clinical", "ehr", "hl7", "fhir", "patient"],
    "ecommerce": ["e-commerce", "ecommerce", "retail", "marketplace", "shopify"],
    "security": ["security", "infosec", "cyber", "iam", "zerotrust", "zero trust"],
    "ml_ai": ["machine learning", "ml", "ai", "llm", "rag", "genai", "nlp", "vision"],
    "data": ["data platform", "analytics", "data engineering", "etl", "elt", "warehouse"],
}

# Seniority keywords
SENIORITY_KEYWORDS = {
    "principal": ["principal"],
    "staff": ["staff"],
    "lead": ["lead", "manager"],
    "senior": ["senior", "sr"],
    "mid": ["mid-level", "mid level", "mid"],
    "junior": ["junior", "jr"],
}

def put_text(text: str) -> str:
    """Store resume text and return a token.

    Note the absence of logging. This handles a named person's CV — their employers,
    education and contact details. Logging its size, its token or (worse) a preview
    of it writes PII into wherever the logs end up. There is nothing here worth the
    risk of that.
    """
    tok = uuid.uuid4().hex
    _remember(_CACHE, tok, text)
    _INSIGHTS_CACHE.pop(tok, None)
    return tok

def get_text(token: str) -> Optional[str]:
    """Retrieve resume text by token"""
    return _CACHE.get(token)

# .title() would render these as "Nlp", "Rag", "Aws" — which looks broken on a
# skill chip. Anything not listed here falls back to .title() as before.
SKILL_DISPLAY_NAMES = {
    "nlp": "NLP", "rag": "RAG", "llm": "LLM", "aws": "AWS", "gcp": "GCP",
    "sql": "SQL", "html": "HTML", "css": "CSS", "ci/cd": "CI/CD", "api": "API",
    "rest api": "REST API", "graphql": "GraphQL", "grpc": "gRPC", "gpt": "GPT",
    "bert": "BERT", "ml": "ML", "ai": "AI", "etl": "ETL", "iam": "IAM",
    "javascript": "JavaScript", "typescript": "TypeScript", "postgresql": "PostgreSQL",
    "mysql": "MySQL", "mongodb": "MongoDB", "dynamodb": "DynamoDB",
    "node.js": "Node.js", "next.js": "Next.js", "asp.net": "ASP.NET",
    "tensorflow": "TensorFlow", "pytorch": "PyTorch", "scikit-learn": "scikit-learn",
    "c++": "C++", "c#": "C#", "github": "GitHub", "gitlab": "GitLab",
    "kubernetes": "Kubernetes", "elasticsearch": "Elasticsearch",
}


def _display_skill(keyword: str) -> str:
    return SKILL_DISPLAY_NAMES.get(keyword.lower(), keyword.title())


def _extract_keywords(text: str, keywords: List[str]) -> List[str]:
    """Return unique keywords found in text with basic word-boundary matching."""
    found = set()
    for kw in keywords:
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, text):
            found.add(_display_skill(kw))
    return sorted(found)


def extract_resume_insights(token: str) -> Optional[Dict[str, Any]]:
    """
    Extract role, seniority, categorized skills, domains, tech stack, and years of experience.
    Token-optimized: Uses regex/keyword matching (no external API calls).
    
    Returns:
        {
            "role": str | None,
            "seniority": str | None,
            "skills": {
                "technical": [...],
                "tools": [...],
                "frameworks": [...],
                "soft": [...]
            },
            "skills_flat": [...],  # flattened list (backward compatible)
            "domains": [...],
            "tech_stack": [...],
            "years_experience": int
        }
    """
    if token in _INSIGHTS_CACHE:
        return _INSIGHTS_CACHE[token]
    
    text = get_text(token)
    if not text:
        return None
    
    # Use first 1000 chars for role detection (usually contains title)
    header_text = text[:1000].lower()
    full_text_lower = text.lower()
    
    insights: Dict[str, Any] = {
        "role": None,
        "seniority": None,
        "skills": {
            "technical": [],
            "tools": [],
            "frameworks": [],
            "soft": [],
        },
        "skills_flat": [],
        "domains": [],
        "tech_stack": [],
        "years_experience": 0,
    }
    
    # Extract role/job title (usually in first few lines)
    # Common patterns: "Senior Software Engineer", "AI Engineer", "Full Stack Developer"
    role_patterns = [
        r"(?:senior|junior|lead|principal|staff)?\s*(?:software|ai|ml|data|full.?stack|backend|frontend|devops|cloud|security)?\s*(?:engineer|developer|architect|scientist|analyst|specialist)",
        r"(?:software|ai|ml|data|full.?stack|backend|frontend|devops|cloud|security)?\s*(?:engineer|developer|architect|scientist|analyst|specialist)",
        r"title[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"position[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
    ]
    
    for pattern in role_patterns:
        match = re.search(pattern, header_text, re.IGNORECASE)
        if match:
            role = match.group(1) if match.lastindex else match.group(0)
            # Clean up role
            role = re.sub(r'\s+', ' ', role.strip())
            if len(role) > 5 and len(role) < 50:  # Reasonable role length
                insights["role"] = role.title()
                break
    
    # Extract seniority
    for level, keywords in SENIORITY_KEYWORDS.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', header_text, re.IGNORECASE):
                insights["seniority"] = level
                break
        if insights["seniority"]:
            break
    
    # Extract skills using categorized buckets
    categorized_skills = {}
    for bucket, keywords in SKILL_BUCKETS.items():
        categorized_skills[bucket] = _extract_keywords(full_text_lower, keywords)
    insights["skills"] = categorized_skills
    
    # Flatten skills for backward compatibility
    flat_skills = []
    for vals in categorized_skills.values():
        flat_skills.extend(vals)
    # Add any additional tech keywords not already captured
    extra = _extract_keywords(full_text_lower, TECH_SKILLS_KEYWORDS)
    flat_skills.extend(extra)
    # Deduplicate while preserving order
    seen = set()
    flat_unique = []
    for sk in flat_skills:
        if sk.lower() not in seen:
            seen.add(sk.lower())
            flat_unique.append(sk)
    insights["skills_flat"] = flat_unique
    
    # Domains
    domains_found = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', full_text_lower):
                domains_found.append(domain)
                break
    insights["domains"] = sorted(set(domains_found))
    
    # Refine generic roles based on detected skills
    _role_lower = (insights.get("role") or "").lower().strip()
    _generic_roles = {"engineer", "developer", "analyst", "scientist", "specialist"}
    if _role_lower in _generic_roles or (len(_role_lower) < 15 and "engineer" in _role_lower and not any(p in _role_lower for p in ["software", "ai", "ml", "data", "cloud", "devops", "security", "full", "backend", "frontend", "mobile", "web", "systems", "embedded", "qa", "test", "network", "platform"])):
        if any(s in seen for s in ["python", "tensorflow", "pytorch", "machine learning", "deep learning", "nlp", "llm", "rag", "transformer", "neural networks", "computer vision"]):
            insights["role"] = "AI Engineer"
        elif any(s in seen for s in ["react", "vue", "angular", "next.js", "typescript", "javascript", "html", "css", "frontend"]):
            insights["role"] = "Software Engineer"
        elif any(s in seen for s in ["django", "flask", "fastapi", "spring", "node.js", "express", "postgresql", "mysql", "mongodb", "backend", "microservices", "rest api", "graphql"]):
            insights["role"] = "Software Engineer"
        elif any(s in seen for s in ["docker", "kubernetes", "aws", "azure", "gcp", "terraform", "ci/cd", "jenkins", "devops"]):
            insights["role"] = "DevOps Engineer"
        elif any(s in seen for s in ["sql", "pandas", "numpy", "tableau", "power bi", "analytics", "data"]):
            insights["role"] = "Data Analyst" if "analyst" in _role_lower else "Software Engineer"
        else:
            insights["role"] = "Software Engineer"  # Default fallback
    
    # Tech stack = top skills (technical + frameworks + tools)
    tech_stack = []
    for bucket in ["technical", "frameworks", "tools"]:
        tech_stack.extend(categorized_skills.get(bucket, []))
    # Keep top 20 unique
    ts_seen = set()
    tech_stack_unique = []
    for sk in tech_stack:
        if sk.lower() not in ts_seen:
            ts_seen.add(sk.lower())
            tech_stack_unique.append(sk)
    insights["tech_stack"] = tech_stack_unique[:20]
    
    # Extract years of experience
    # Patterns: "5 years", "5+ years", "5 yrs", "experience: 5"
    exp_patterns = [
        r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)",
        r"(?:experience|exp)[:\s]+(\d+)\+?\s*(?:years?|yrs?)",
        r"(\d+)\+?\s*(?:years?|yrs?)\s*(?:in|with)",
    ]
    
    max_years = 0
    for pattern in exp_patterns:
        matches = re.finditer(pattern, full_text_lower)
        for match in matches:
            years = int(match.group(1))
            max_years = max(max_years, years)
    
    # Also try to estimate from date ranges (e.g., "2020 - 2024" = 4 years)
    date_pattern = r"(\d{4})\s*[-–—]\s*(\d{4}|present|current)"
    date_matches = re.finditer(date_pattern, text, re.IGNORECASE)
    total_years = 0
    for match in date_matches:
        start_year = int(match.group(1))
        end_str = match.group(2).lower()
        if end_str in ["present", "current"]:
            from datetime import datetime
            end_year = datetime.now().year
        else:
            end_year = int(end_str)
        total_years += (end_year - start_year)
    
    if total_years > 0:
        insights["years_experience"] = max(max_years, total_years // 2)  # Divide by 2 to account for overlapping roles
    else:
        insights["years_experience"] = max_years
    
    # Backward compatibility keys
    insights["experience_years"] = insights["years_experience"]
    
    # Cache insights
    _remember(_INSIGHTS_CACHE, token, insights)
    
    # Intentionally not logged — see put_text(). Even a summary of someone's CV
    # (their role, seniority, years of experience) is personal data.
    return insights

def put_profile(token: str, structured: Dict[str, Any]) -> None:
    """Store a structured resume profile (parsed sections) for a token."""
    _remember(_PROFILE_CACHE, token, structured)

def get_profile(token: str) -> Optional[Dict[str, Any]]:
    """Retrieve the structured resume profile for a token, if any."""
    return _PROFILE_CACHE.get(token)

# Tokens a user has uploaded, so "delete my data" can actually reach them.
_USER_TOKENS: Dict[str, set] = {}

def associate_token(user_id: str, token: str) -> None:
    _USER_TOKENS.setdefault(user_id, set()).add(token)

def forget_user(user_id: str) -> int:
    """Drop every resume this user uploaded, from every cache."""
    tokens = _USER_TOKENS.pop(user_id, set())
    for tok in tokens:
        _CACHE.pop(tok, None)
        _INSIGHTS_CACHE.pop(tok, None)
        _PROFILE_CACHE.pop(tok, None)
    return len(tokens)

def clear_cache():
    """Clear all cached resume text (for cleanup)"""
    global _CACHE, _INSIGHTS_CACHE, _PROFILE_CACHE
    _CACHE.clear()
    _INSIGHTS_CACHE.clear()
    _PROFILE_CACHE.clear()
    print("🗑️ Cleared resume cache")
