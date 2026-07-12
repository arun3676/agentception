"""
Focused Company Research Agent for Email Personalization

Goal: Given a company name and homepage URL, quickly gather the most useful
recent context to personalize an outreach email for an AI/ML role.

Always prioritizes:
- What the company actually builds or sells
- Latest product launches, features, blog posts or engineering articles
- Recent AI/LLM/RAG/agentic initiatives, infra work, or open roles
- Culture, mission, and high-level strategy
"""

from __future__ import annotations
import os
import re
import json
from textwrap import dedent
from typing import Dict, Any, Optional
import httpx
from urllib.parse import urlparse, urljoin


class FocusedResearchAgent:
    """
    Focused research agent that gathers context specifically for email personalization.
    Prioritizes high-signal sources and extracts contact information.
    """
    
    # Job boards and aggregators to ignore
    JOB_BOARD_DOMAINS = [
        "greenhouse.io", "boards.greenhouse.io",
        "ashbyhq.com", "jobs.ashbyhq.com",
        "lever.co", "jobs.lever.co",
        "workday.com",
        "indeed.com",
        "glassdoor.com",
        "linkedin.com/jobs",
        "ziprecruiter.com",
        "dice.com",
        "monster.com",
        "careerbuilder.com"
    ]
    
    # Generic aggregator patterns
    AGGREGATOR_PATTERNS = [
        r"top\s+\d+",
        r"best\s+\d+",
        r"salary.*guide",
        r"interview.*questions",
        r"job\s+board"
    ]
    
    # LLM prompt for converting search results to structured intel
    NOTES_FOR_EMAIL_WRITER = dedent("""
    You are a focused company research assistant for an AI job-search agent.

    You receive:
    - The company name and (optionally) the job title.
    - A list of web page snippets from:
      - The company homepage
      - Product / careers / blog / news pages
      - The specific job posting when available

    Your job is to compress this into a **small JSON object** that will be fed into an email-writer model.

    Rules:
    - Be concrete and specific.
    - Prefer **recent** items (last 12–18 months) when possible.
    - Never mention article titles, dates, or sources directly in the final text (no links, no "I read on your site…").
    - Do NOT output explanations, only JSON.

    Return JSON with exactly these keys:

    {
      "COMPANY_SUMMARY": "1–2 short sentences describing what the company does and who it serves.",
      "RECENT_WORK": [
        "One sentence about a recent project, product launch, or initiative.",
        "Optional second bullet.",
        "Optional third bullet."
      ],
      "AI_OR_TECH_FOCUS": "Short summary of the main AI / data / platform themes (e.g., 'LLM-powered support tooling, RAG over docs, multi-tenant SaaS on AWS').",
      "BEST_CONTACT_NAME": "Best guess at a human name to address in email (founder, hiring manager, or generic like 'Hiring Manager').",
      "BEST_CONTACT_EMAIL": "Best guess at a contact email that is valid for outreach (prefer people@company or jobs@company over generic board emails)."
    }

    If you are not sure about a field, keep it brief but still fill it (e.g. 'Hiring Manager', 'careers@company.com').
    Do NOT include any fields other than the ones above.
    """)
    
    def __init__(self, emit=None):
        """Initialize the research agent"""
        self.emit = emit
        self.http_client = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.http_client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.http_client:
            await self.http_client.aclose()
    
    async def research_company(
        self,
        company_name: str,
        homepage_url: str,
        target_role_title: str,
        job_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Research a company and return structured information for email personalization.
        
        Args:
            company_name: Name of the company
            homepage_url: Company homepage URL
            target_role_title: Target role (e.g., "AI Engineer", "LLM Engineer")
            job_url: Optional URL to the specific job posting
            
        Returns:
            Dictionary with keys:
            - COMPANY_SUMMARY: 1-2 line summary
            - RECENT_WORK: List of strings (recent projects/initiatives)
            - AI_OR_TECH_FOCUS: AI/LLM/infra focus or "none found"
            - BEST_CONTACT_NAME: Name or "Hiring Manager"
            - BEST_CONTACT_EMAIL: Email or "unknown"
        """
        
        if self.emit:
            await self.emit(f"🔍 Researching {company_name} for {target_role_title} role...")
        
        # Parse homepage domain for domain-specific searches
        try:
            parsed_url = urlparse(homepage_url)
            domain = parsed_url.netloc or parsed_url.path
            domain = domain.replace("www.", "").split("/")[0]  # Get just the domain
        except:
            domain = homepage_url
        
        # Search strategy: Focus on official sources with targeted queries
        search_results = await self._search_official_sources(
            company_name, domain, target_role_title, job_url
        )
        
        # Use LLM to extract structured intel from search results
        research_data = await self._extract_intel_with_llm(
            company_name, target_role_title, search_results, job_url
        )
        
        if self.emit:
            await self.emit(f"✅ Research complete for {company_name}")
        
        return research_data
    
    async def _search_official_sources(
        self,
        company_name: str,
        domain: str,
        target_role: str,
        job_url: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """
        Search for high-signal sources: official site, blog, careers, products, engineering.
        Uses Tavily search with targeted queries focused on the company domain.
        """
        
        from ..tools.tavily_search import tavily_search
        
        results = []
        
        # Build targeted search queries prioritizing official sources
        queries = [
            f"{company_name} official website",
            f"{company_name} engineering blog",
            f"{company_name} AI platform",
            f"{company_name} product updates",
        ]
        
        # If we have a job URL, fetch it directly
        if job_url:
            try:
                # Try to fetch the job posting content
                async with httpx.AsyncClient(timeout=15.0) as client:
                    response = await client.get(job_url)
                    if response.status_code == 200:
                        # Add job posting as a result
                        results.append({
                            "title": f"{target_role} at {company_name}",
                            "url": job_url,
                            "content": response.text[:5000],  # Limit content size
                            "summary": f"Job posting for {target_role} position at {company_name}",
                            "score": 1.0
                        })
            except Exception as e:
                if self.emit:
                    await self.emit(f"⚠️ Failed to fetch job URL: {e}")
        
        # Execute searches with domain filtering
        for query in queries[:4]:  # Limit to 4 queries to stay fast
            try:
                # Use Tavily with domain filtering
                search_results = await tavily_search(
                    query,
                    num_results=2,  # Get 2 results per query (total ~8 results)
                    search_depth="basic",
                    include_domains=[domain] if domain else None,
                    exclude_domains=self.JOB_BOARD_DOMAINS
                )
                
                # Filter out job boards and aggregators, prioritize company domain
                for result in search_results:
                    url = result.get("url", "")
                    if self._is_quality_source(url, domain):
                        # Transform Tavily format to match expected structure
                        results.append({
                            "title": result.get("title", ""),
                            "url": url,
                            "content": result.get("content", ""),
                            "summary": result.get("content", "")[:500],  # Use content as summary
                            "score": result.get("score", 0.0)
                        })
                        
            except Exception as e:
                if self.emit:
                    await self.emit(f"⚠️ Search query failed: {query[:50]}... - {e}")
                continue
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_results = []
        for result in results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)
        
        # Sort by score (if available) and limit to 6 high-quality pages
        unique_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        
        if self.emit:
            await self.emit(f"✅ Found {len(unique_results)} quality sources for {company_name}")
        
        return unique_results[:6]  # Keep result list short (3-6 high quality pages)
    
    def _is_quality_source(self, url: str, domain: str) -> bool:
        """Check if URL is from a quality source (not job board or aggregator)"""
        
        if not url:
            return False
        
        url_lower = url.lower()
        
        # Reject job boards
        for job_board in self.JOB_BOARD_DOMAINS:
            if job_board in url_lower:
                return False
        
        # Reject aggregator patterns
        for pattern in self.AGGREGATOR_PATTERNS:
            if re.search(pattern, url_lower):
                return False
        
        # Prefer official domain sources
        if domain and domain in url_lower:
            return True
        
        # Prefer /blog, /news, /stories, /careers paths
        quality_paths = ["/blog", "/news", "/stories", "/careers", "/about", "/product"]
        if any(path in url_lower for path in quality_paths):
            return True
        
        # Accept other sources if they look legitimate
        return True
    
    async def _extract_intel_with_llm(
        self,
        company_name: str,
        target_role: str,
        search_results: list[Dict[str, Any]],
        job_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Use LLM to extract structured intel from search results.
        Returns JSON with COMPANY_SUMMARY, RECENT_WORK, AI_OR_TECH_FOCUS, etc.
        """
        
        DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY")
        if not DEEPSEEK_KEY:
            # Fallback to basic extraction if no API key
            return self._extract_intel_fallback(company_name, search_results)
        
        # Format search results for LLM
        snippets = []
        for i, result in enumerate(search_results[:6], 1):
            title = result.get("title", "")
            content = result.get("content", "") or result.get("summary", "")
            url = result.get("url", "")
            
            # Limit content length
            content_preview = content[:800] if len(content) > 800 else content
            
            snippets.append(f"Page {i} ({url}):\nTitle: {title}\nContent: {content_preview}")
        
        search_context = "\n\n".join(snippets)
        
        # Build prompt
        prompt = f"""{self.NOTES_FOR_EMAIL_WRITER}

Company name: {company_name}
Job title: {target_role}
{f'Job posting URL: {job_url}' if job_url else ''}

Search results from company pages:

{search_context}

Now extract the structured information and return ONLY valid JSON (no markdown, no code blocks, no explanations):
"""
        
        # Call LLM
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.deepseek.com/chat/completions",
                    headers={
                        "Authorization": f"Bearer {DEEPSEEK_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,  # Lower temperature for more consistent JSON
                        "max_tokens": 600
                    }
                )
                response.raise_for_status()
                text = response.json()["choices"][0]["message"]["content"]
            
            # Parse JSON from response (may be wrapped in markdown code blocks)
            # Remove markdown code blocks if present
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            
            # Try to extract JSON object
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                json_str = json_match.group(0)
                research_data = json.loads(json_str)
            else:
                # Try parsing the whole text
                research_data = json.loads(text)
            
            # Validate and normalize structure
            result = {
                "COMPANY_SUMMARY": research_data.get("COMPANY_SUMMARY", f"{company_name} - technology company"),
                "RECENT_WORK": research_data.get("RECENT_WORK", []),
                "AI_OR_TECH_FOCUS": research_data.get("AI_OR_TECH_FOCUS", "none found"),
                "BEST_CONTACT_NAME": research_data.get("BEST_CONTACT_NAME", "Hiring Manager"),
                "BEST_CONTACT_EMAIL": research_data.get("BEST_CONTACT_EMAIL", "unknown")
            }
            
            # Ensure RECENT_WORK is a list
            if isinstance(result["RECENT_WORK"], str):
                # Split string into list if it's a single string
                result["RECENT_WORK"] = [result["RECENT_WORK"]]
            elif not isinstance(result["RECENT_WORK"], list):
                result["RECENT_WORK"] = []
            
            return result
            
        except json.JSONDecodeError as e:
            if self.emit:
                await self.emit(f"⚠️ Failed to parse LLM JSON response: {e}")
            print(f"⚠️ JSON parse error: {e}, response: {text[:200]}")
            return self._extract_intel_fallback(company_name, search_results)
        except Exception as e:
            if self.emit:
                await self.emit(f"⚠️ LLM extraction failed: {e}")
            print(f"⚠️ LLM extraction error: {e}")
            return self._extract_intel_fallback(company_name, search_results)
    
    def _extract_intel_fallback(
        self,
        company_name: str,
        search_results: list[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fallback extraction if LLM fails - uses simple regex-based extraction"""
        
        # Basic extraction from first result
        company_summary = f"{company_name} - technology company"
        if search_results:
            first_content = search_results[0].get("content", "") or search_results[0].get("summary", "")
            if first_content:
                # Take first sentence as summary
                sentences = re.split(r'[.!?]+', first_content)
                if sentences:
                    company_summary = sentences[0].strip()[:200]
        
        return {
            "COMPANY_SUMMARY": company_summary,
            "RECENT_WORK": [],
            "AI_OR_TECH_FOCUS": "none found",
            "BEST_CONTACT_NAME": "Hiring Manager",
            "BEST_CONTACT_EMAIL": "unknown"
        }
    
    def _extract_company_summary(
        self,
        results: list[Dict[str, Any]],
        company_name: str
    ) -> str:
        """Extract a 1-2 line company summary from search results"""
        
        summaries = []
        
        for result in results[:3]:  # Check first 3 results
            title = result.get("title", "")
            summary = result.get("summary", "")
            text = f"{title} {summary}"
            
            # Look for company description patterns
            # Usually found in "About" pages, homepage, or company descriptions
            
            # Extract if we find common description markers
            if any(marker in text.lower() for marker in [
                "builds", "develops", "creates", "provides", "offers",
                "company", "startup", "platform", "product", "service"
            ]):
                # Clean up the text - take first sentence or two
                sentences = re.split(r'[.!?]+', text)
                relevant_sentences = [
                    s.strip() for s in sentences[:2]
                    if len(s.strip()) > 20 and company_name.lower() in s.lower()
                ]
                
                if relevant_sentences:
                    summaries.append(" ".join(relevant_sentences))
        
        # Return best summary or generate one
        if summaries:
            return summaries[0][:300]  # Limit length
        
        return f"{company_name} - technology company focused on innovation and growth."
    
    def _extract_recent_work(
        self,
        results: list[Dict[str, Any]],
        target_role: str
    ) -> str:
        """Extract 2-4 concrete recent things they're working on"""
        
        recent_items = []
        
        for result in results[:5]:  # Check first 5 results
            title = result.get("title", "")
            summary = result.get("summary", "")
            highlights = result.get("highlights", [])
            
            combined_text = f"{title} {summary} {' '.join(highlights) if highlights else ''}"
            
            # Look for indicators of recent work
            recent_keywords = [
                "launch", "release", "announce", "introduce", "unveil",
                "new feature", "new product", "updated", "enhanced",
                "2024", "2025", "recently", "latest", "now", "currently"
            ]
            
            # Check if this result mentions recent work
            if any(keyword in combined_text.lower() for keyword in recent_keywords):
                # Extract the key point (first sentence or highlight)
                sentences = re.split(r'[.!?]+', combined_text)
                
                for sentence in sentences[:2]:
                    sentence = sentence.strip()
                    if len(sentence) > 30 and len(sentence) < 200:
                        # Check if it's actually about recent work
                        if any(keyword in sentence.lower() for keyword in recent_keywords):
                            recent_items.append(sentence)
                            if len(recent_items) >= 4:
                                break
            
            if len(recent_items) >= 4:
                break
        
        # Format as paragraph
        if recent_items:
            return " ".join(recent_items[:4])
        
        return "No specific recent work information found in available sources."
    
    def _extract_ai_tech_focus(
        self,
        results: list[Dict[str, Any]],
        target_role: str
    ) -> str:
        """Extract what they're doing in AI/LLM/infra if any"""
        
        ai_keywords = [
            "AI", "artificial intelligence", "machine learning", "ML",
            "LLM", "large language model", "GPT", "transformer",
            "RAG", "retrieval augmented generation",
            "agentic", "agents", "autonomous agents",
            "infrastructure", "infra", "MLOps", "ML infrastructure"
        ]
        
        ai_mentions = []
        
        for result in results[:5]:
            title = result.get("title", "")
            summary = result.get("summary", "")
            text = f"{title} {summary}".lower()
            
            # Check for AI-related keywords
            found_keywords = [kw for kw in ai_keywords if kw.lower() in text]
            
            if found_keywords:
                # Extract relevant sentence
                sentences = re.split(r'[.!?]+', f"{title} {summary}")
                for sentence in sentences[:2]:
                    sentence_lower = sentence.lower()
                    if any(kw.lower() in sentence_lower for kw in found_keywords):
                        if len(sentence.strip()) > 20:
                            ai_mentions.append(sentence.strip())
                            break
        
        if ai_mentions:
            return " ".join(ai_mentions[:2])  # Combine top mentions
        
        return "none found"
    
    async def _extract_contact_info(
        self,
        company_name: str,
        domain: str,
        results: list[Dict[str, Any]]
    ) -> Dict[str, str]:
        """Extract best contact options: named hiring manager/recruiter or generic email"""
        
        contact_info = {"name": "unknown", "email": "unknown"}
        
        # First, try to find named contacts in search results
        for result in results[:5]:
            text = f"{result.get('title', '')} {result.get('summary', '')}"
            
            # Look for email patterns with names
            # Pattern: Name <email> or email (Name)
            email_pattern = r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s*[<\(]?\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            matches = re.findall(email_pattern, text)
            
            if matches:
                for name, email in matches[:1]:  # Take first match
                    # Check if it's a hiring-related contact
                    text_lower = text.lower()
                    if any(word in text_lower for word in [
                        "hiring", "recruiter", "talent", "careers", "jobs"
                    ]):
                        contact_info["name"] = name
                        contact_info["email"] = email
                        return contact_info
            
            # Look for standalone emails with context
            email_only_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            emails = re.findall(email_only_pattern, text)
            
            for email in emails[:1]:
                # Check if it's a careers/hiring email
                if any(domain in email for domain in [
                    "careers", "jobs", "talent", "hiring", "recruiting", "people"
                ]):
                    contact_info["email"] = email
                    # Try to extract name from context
                    name_pattern = r'([A-Z][a-z]+\s+[A-Z][a-z]+)'
                    name_match = re.search(name_pattern, text[:200])  # Check first 200 chars
                    if name_match:
                        contact_info["name"] = name_match.group(1)
                    return contact_info
        
        # If no contact found, try to guess from domain
        if domain and contact_info["email"] == "unknown":
            guessed_email = self._guess_contact_email(domain)
            if guessed_email:
                contact_info["email"] = f"{guessed_email} (guessed)"  # Mark as guess
        
        return contact_info
    
    def _guess_contact_email(self, domain: str) -> Optional[str]:
        """
        Guess contact email based on domain and common patterns.
        Note: This is a guess - should be marked clearly when returned.
        """
        
        # Clean domain (remove www., http://, etc.)
        domain = domain.replace("www.", "").replace("http://", "").replace("https://", "")
        domain = domain.split("/")[0]  # Take only domain part
        domain = domain.strip()
        
        if not domain:
            return None
        
        # Common patterns in priority order
        patterns = [
            "careers",
            "jobs",
            "talent",
            "hiring",
            "recruiting",
            "people",
            "hr"
        ]
        
        # Return first pattern (most common)
        return f"{patterns[0]}@{domain}"
    
    def format_output_plain_text(self, research_data: Dict[str, str]) -> str:
        """
        Format research data as plain text output exactly as specified.
        No markdown, no bullet symbols, plain text only.
        
        Output format:
        COMPANY_SUMMARY: <1–2 line summary>
        RECENT_WORK: <short paragraph with 2–4 concrete, recent things>
        AI_OR_TECH_FOCUS: <what they are doing in AI/LLM/infra if any, else "none found">
        BEST_CONTACT_NAME: <name or "unknown">
        BEST_CONTACT_EMAIL: <email or best guess or "unknown">
        NOTES_FOR_EMAIL_WRITER: <1 short paragraph of extra flavor useful for a cold email>
        """
        
        lines = [
            f"COMPANY_SUMMARY: {research_data.get('COMPANY_SUMMARY', '')}",
            f"RECENT_WORK: {research_data.get('RECENT_WORK', '')}",
            f"AI_OR_TECH_FOCUS: {research_data.get('AI_OR_TECH_FOCUS', 'none found')}",
            f"BEST_CONTACT_NAME: {research_data.get('BEST_CONTACT_NAME', 'unknown')}",
            f"BEST_CONTACT_EMAIL: {research_data.get('BEST_CONTACT_EMAIL', 'unknown')}",
            f"NOTES_FOR_EMAIL_WRITER: {research_data.get('NOTES_FOR_EMAIL_WRITER', '')}"
        ]
        
        return "\n\n".join(lines)
    
    def _generate_email_writer_notes(
        self,
        company_summary: str,
        recent_work: str,
        ai_tech_focus: str
    ) -> str:
        """Generate extra flavor notes useful for cold email personalization"""
        
        notes_parts = []
        
        # Highlight AI/tech focus if found
        if ai_tech_focus and ai_tech_focus != "none found":
            notes_parts.append(f"Strong focus on {ai_tech_focus.lower()}.")
        
        # Mention recent work if available
        if recent_work and "No specific" not in recent_work:
            # Extract key points from recent work
            sentences = re.split(r'[.!?]+', recent_work)
            key_sentences = [s.strip() for s in sentences[:2] if len(s.strip()) > 20]
            if key_sentences:
                notes_parts.append(f"Recently: {key_sentences[0]}")
        
        # Add company summary if we have good info
        if company_summary and len(company_summary) > 30:
            notes_parts.append(company_summary[:150])
        
        if notes_parts:
            return " ".join(notes_parts)
        
        return "Limited information available. Focus on general fit and enthusiasm for the role."

