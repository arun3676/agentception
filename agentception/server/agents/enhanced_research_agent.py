"""
Enhanced Research Agent for Multi-Source Company Intelligence
Gathers competitive analysis, funding, tech stack, team, and market positioning
"""

from __future__ import annotations
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import re
import httpx
from datetime import datetime

# 🧠 CODING THINKING: Why use a class instead of functions?
# 1. State management - can store configuration, cache, etc.
# 2. Extensibility - easy to add new intelligence types
# 3. Testing - easier to mock and test individual components
# 4. Reusability - can be instantiated with different configs

class IntelligenceType(Enum):
    """Different types of intelligence we can gather"""
    BASIC_INFO = "basic_info"           # Name, description, homepage (existing)
    COMPETITIVE = "competitive"         # Who are their competitors?
    FUNDING = "funding"                 # Recent funding, valuation, growth stage
    TEAM = "team"                      # Key people, hiring patterns
    TECH_STACK = "tech_stack"          # What technology do they use?
    MARKET_POSITION = "market_position" # Market positioning, target audience
    RECENT_NEWS = "recent_news"         # Latest company news and announcements
    PRODUCT_ROADMAP = "product_roadmap" # Product updates and future plans
    CULTURE = "culture"                 # Company culture and values
    GROWTH_METRICS = "growth_metrics"   # Growth indicators and metrics
    
    def __hash__(self):
        return hash(self.value)

@dataclass
class CompanyIntelligence:
    """Enhanced company intelligence with multiple data sources"""
    # Basic info (existing)
    name: str
    description: str
    homepage: str
    city: str
    source_url: str = ""
    tags: List[str] = None
    contact_hint: str = None
    score: float = 0.0
    
    # Enhanced intelligence (new)
    competitors: List[str] = None
    funding_stage: str = None
    last_funding: str = None
    key_people: List[Dict[str, str]] = None
    tech_stack: List[str] = None
    market_position: str = None
    company_size: str = None
    growth_indicator: str = None
    
    # Advanced research features (new)
    recent_news: List[str] = None
    product_updates: List[str] = None
    company_culture: str = None
    growth_metrics: Dict[str, str] = None
    
    # Metadata
    confidence_score: float = 0.0
    data_sources: List[str] = None
    last_updated: str = None
    
    def __post_init__(self):
        if self.competitors is None:
            self.competitors = []
        if self.key_people is None:
            self.key_people = []
        if self.tech_stack is None:
            self.tech_stack = []
        if self.tags is None:
            self.tags = []
        if self.data_sources is None:
            self.data_sources = []
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()

class EnhancedResearchAgent:
    """
    Enhanced research agent that gathers multi-source intelligence
    """
    
    def __init__(self, emit=None, run_id=None):
        # 🧠 CODING THINKING: Why store these as instance variables?
        # 1. Performance - reuse HTTP clients, avoid re-initialization
        # 2. Configuration - can be customized per instance
        # 3. Caching - can store intermediate results
        self.http_client = None
        self.emit = emit
        self.run_id = run_id
        self.intelligence_cache = {}  # Cache results to avoid duplicate API calls
        
    async def __aenter__(self):
        """Async context manager for proper resource cleanup"""
        self.http_client = httpx.AsyncClient(timeout=30)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up HTTP client"""
        if self.http_client:
            await self.http_client.aclose()
    
    async def analyze_companies(
        self, 
        companies: List[Dict[str, Any]], 
        intelligence_types: List[IntelligenceType] = None,
        emit: callable = None
    ) -> List[CompanyIntelligence]:
        """
        Analyze companies with multiple intelligence sources
        
        🧠 CODING THINKING: Why use asyncio.gather() here?
        1. Parallel execution - analyze multiple companies simultaneously
        2. Fault tolerance - if one company fails, others continue
        3. Performance - much faster than sequential processing
        4. Scalability - can handle many companies efficiently
        """
        
        if intelligence_types is None:
            # Reduced intelligence types to save credits - focus on most valuable
            intelligence_types = [
                IntelligenceType.RECENT_NEWS,      # Most valuable for personalization
                IntelligenceType.TECH_STACK,      # Relevant for tech roles
                IntelligenceType.FUNDING         # Shows company health
            ]
        
        if self.emit:
            await self.emit(f"🔍 Enhanced analysis: {len(companies)} companies, {len(intelligence_types)} intelligence types")
        
        # 🧠 CODING THINKING: Why process companies in parallel?
        # Each company analysis is independent, so we can run them concurrently
        tasks = [
            self._analyze_single_company(company, intelligence_types)
            for company in companies
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and return successful results
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                if self.emit:
                    await self.emit(f"❌ Analysis failed for {companies[i].get('name', 'Unknown')}: {result}")
            else:
                successful_results.append(result)
        
        if self.emit:
            await self.emit(f"✅ Enhanced analysis complete: {len(successful_results)} companies analyzed")
        
        return successful_results
    
    async def _analyze_single_company(
        self, 
        company: Dict[str, Any], 
        intelligence_types: List[IntelligenceType],
        emit: callable = None
    ) -> CompanyIntelligence:
        """
        Analyze a single company with multiple intelligence sources
        
        🧠 CODING THINKING: Why run intelligence gathering in parallel?
        1. Each intelligence type is independent
        2. Some sources might be slow (API calls, web scraping)
        3. If one source fails, others can still provide value
        4. Much faster than sequential processing
        """
        
        company_name = company.get("name", "Unknown")
        
        if self.emit:
            await self.emit(f"  📊 Analyzing {company_name} with {len(intelligence_types)} intelligence sources...")
        
        # 🧠 CODING THINKING: Why use a dictionary for intelligence gathering?
        # 1. Easy to add new intelligence types
        # 2. Can run them in parallel with asyncio.gather()
        # 3. Easy to handle partial failures
        intelligence_tasks = []
        
        for intel_type in intelligence_types:
            intelligence_tasks.append(self._gather_intelligence(company, intel_type, emit))

        # Gather intelligence concurrently
        results = await asyncio.gather(*intelligence_tasks, return_exceptions=True)

        # Process results
        intel_data = {}
        data_sources = []
        for intel_type, result in zip(intelligence_types, results):
            if isinstance(result, Exception):
                if self.emit:
                    await self.emit(f"    - ⚠️ Error gathering {intel_type.value}: {result}")
            else:
                intel_data.update(result)
                data_sources.append(intel_type.value)
                if self.emit:
                    await self.emit(f"    - ✅ Gathered {intel_type.value}")
        
        # 🧠 CODING THINKING: Why calculate confidence score?
        # 1. Helps rank companies by data quality
        # 2. Useful for filtering low-quality results
        # 3. Helps users understand how reliable the data is
        confidence_score = len(data_sources) / len(intelligence_types)
        
        return CompanyIntelligence(
            name=company.get("name", ""),
            description=company.get("blurb", ""),
            homepage=company.get("homepage", ""),
            city=company.get("city", ""),
            source_url=company.get("source_url", ""),
            tags=company.get("tags", []),
            contact_hint=company.get("contact_hint"),
            score=company.get("score", 0.0),
            competitors=intel_data.get("competitors", []),
            funding_stage=intel_data.get("funding_stage"),
            last_funding=intel_data.get("last_funding"),
            key_people=intel_data.get("key_people", []),
            tech_stack=intel_data.get("tech_stack", []),
            market_position=intel_data.get("market_position"),
            company_size=intel_data.get("company_size"),
            growth_indicator=intel_data.get("growth_indicator"),
            recent_news=intel_data.get("recent_news", []),
            product_updates=intel_data.get("product_updates", []),
            company_culture=intel_data.get("company_culture"),
            growth_metrics=intel_data.get("growth_metrics", {}),
            confidence_score=confidence_score,
            data_sources=data_sources
        )
    
    async def _gather_intelligence(
        self, 
        company: Dict[str, Any], 
        intel_type: IntelligenceType,
        emit: callable = None
    ) -> Dict[str, Any]:
        """
        Gather specific type of intelligence for a company
        
        🧠 CODING THINKING: Why use a switch-like pattern here?
        1. Easy to add new intelligence types
        2. Clear separation of concerns
        3. Each type can have different error handling
        4. Easy to test individual intelligence types
        """
        
        company_name = company.get("name", "")
        
        try:
            if intel_type == IntelligenceType.COMPETITIVE:
                return await self._analyze_competitors(company)
            elif intel_type == IntelligenceType.FUNDING:
                return await self._analyze_funding(company)
            elif intel_type == IntelligenceType.TEAM:
                return await self._analyze_team(company)
            elif intel_type == IntelligenceType.TECH_STACK:
                return await self._analyze_tech_stack(company)
            elif intel_type == IntelligenceType.MARKET_POSITION:
                return await self._analyze_market_position(company)
            elif intel_type == IntelligenceType.RECENT_NEWS:
                return await self._analyze_recent_news(company)
            elif intel_type == IntelligenceType.PRODUCT_ROADMAP:
                return await self._analyze_product_roadmap(company)
            elif intel_type == IntelligenceType.CULTURE:
                return await self._analyze_culture(company)
            elif intel_type == IntelligenceType.GROWTH_METRICS:
                return await self._analyze_growth_metrics(company)
            else:
                return {}
                
        except Exception as e:
            if emit:
                emit(f"    ⚠️ {intel_type.value} analysis failed for {company_name}: {e}")
            return {}
    
    async def _analyze_competitors(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find competitors using Exa search
        
        🧠 CODING THINKING: Why search for competitors this way?
        1. "competitors of X" is a common search pattern
        2. Exa can find articles comparing companies
        3. More reliable than trying to parse company websites
        4. Can find indirect competitors we might miss
        """
        
        from server.tools.exa_search import exa_search
        
        company_name = company.get("name", "")
        
        # Search for competitor mentions
        # Single comprehensive competitor query to save credits
        competitor_queries = [
            f'"{company_name}" competitors alternatives'
        ]
        
        competitors = set()
        
        for query in competitor_queries:
            try:
                results = await exa_search(query, num_results=2, want_highlights=True)  # Reduced from 3 to 2
                
                # Extract competitor names from results
                for result in results:
                    text = f"{result.get('title', '')} {result.get('summary', '')}"
                    
                    # Simple pattern matching to find company names
                    # 🧠 CODING THINKING: Why use regex here?
                    # 1. Company names often follow patterns (Capitalized, Inc, LLC, etc.)
                    # 2. Need to filter out the target company itself
                    # 3. Can extract multiple competitors from one result
                    company_pattern = r'\b([A-Z][a-zA-Z0-9\s&]+(?:Inc|LLC|Corp|Ltd|AI|Tech|Software|Systems)?)\b'
                    matches = re.findall(company_pattern, text)
                    
                    for match in matches:
                        clean_match = match.strip()
                        if (clean_match.lower() != company_name.lower() and 
                            len(clean_match) > 2 and 
                            len(clean_match) < 50):
                            competitors.add(clean_match)
                            
            except Exception:
                continue
        
        return {"competitors": list(competitors)[:5]}  # Limit to top 5
    
    async def _analyze_funding(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze funding information
        
        🧠 CODING THINKING: Why search for funding information?
        1. Funding stage indicates company maturity
        2. Recent funding = likely hiring
        3. Valuation helps understand company size
        4. Funding news is often publicly available
        """
        
        from server.tools.exa_search import exa_search
        
        company_name = company.get("name", "")
        
        # Single funding query to save credits
        funding_queries = [
            f'"{company_name}" funding investment series'
        ]
        
        funding_info = {}
        
        for query in funding_queries:
            try:
                results = await exa_search(query, num_results=2, want_highlights=True)  # Reduced from 3 to 2
                
                for result in results:
                    text = f"{result.get('title', '')} {result.get('summary', '')}"
                    text_lower = text.lower()
                    
                    # 🧠 CODING THINKING: Why use pattern matching for funding?
                    # 1. Funding announcements follow predictable patterns
                    # 2. Can extract dollar amounts, rounds, dates
                    # 3. More reliable than trying to parse structured data
                    
                    # Look for funding stages
                    if any(stage in text_lower for stage in ['seed', 'series a', 'series b', 'series c']):
                        if 'seed' in text_lower:
                            funding_info['funding_stage'] = 'Seed'
                        elif 'series a' in text_lower:
                            funding_info['funding_stage'] = 'Series A'
                        elif 'series b' in text_lower:
                            funding_info['funding_stage'] = 'Series B'
                        elif 'series c' in text_lower:
                            funding_info['funding_stage'] = 'Series C'
                    
                    # Look for funding amounts
                    amount_match = re.search(r'\$(\d+(?:\.\d+)?[MB])', text)
                    if amount_match:
                        funding_info['last_funding'] = amount_match.group(1)
                        
            except Exception:
                continue
        
        return funding_info
    
    async def _analyze_tech_stack(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze technology stack from job postings and website
        
        🧠 CODING THINKING: Why analyze tech stack?
        1. Helps match candidate skills to company needs
        2. Shows company's technical sophistication
        3. Useful for personalizing outreach emails
        4. Indicates company's technical direction
        """
        
        from server.tools.exa_search import exa_search
        
        company_name = company.get("name", "")
        
        # Single tech stack query to save credits
        tech_queries = [
            f'"{company_name}" technology stack engineering'
        ]
        
        tech_stack = set()
        
        # Common tech stack keywords
        tech_keywords = [
            'python', 'javascript', 'typescript', 'react', 'node.js', 'aws', 'gcp', 'azure',
            'docker', 'kubernetes', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
            'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy', 'fastapi', 'django',
            'flask', 'express', 'vue.js', 'angular', 'spring', 'java', 'go', 'rust',
            'terraform', 'ansible', 'jenkins', 'github actions', 'ci/cd'
        ]
        
        for query in tech_queries:
            try:
                results = await exa_search(query, num_results=2, want_highlights=True)  # Reduced from 3 to 2
                
                for result in results:
                    text = f"{result.get('title', '')} {result.get('summary', '')}"
                    text_lower = text.lower()
                    
                    # Find mentioned technologies
                    for tech in tech_keywords:
                        if tech in text_lower:
                            tech_stack.add(tech)
                            
            except Exception:
                continue
        
        return {"tech_stack": list(tech_stack)}
    
    async def _analyze_team(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze team composition and key people
        
        🧠 CODING THINKING: Why analyze team?
        1. Shows company growth trajectory
        2. Helps identify key contacts for outreach
        3. Indicates hiring patterns and needs
        4. Shows company culture and structure
        """
        
        from server.tools.exa_search import exa_search
        
        company_name = company.get("name", "")
        
        team_queries = [
            f'"{company_name}" team founders',
            f'"{company_name}" hiring engineers',
            f'"{company_name}" team size',
            f'"{company_name}" employees'
        ]
        
        team_info = {}
        
        for query in team_queries:
            try:
                results = await exa_search(query, num_results=2, want_highlights=True)  # Reduced from 3 to 2
                
                for result in results:
                    text = f"{result.get('title', '')} {result.get('summary', '')}"
                    text_lower = text.lower()
                    
                    # Look for team size indicators
                    size_patterns = [
                        r'(\d+)\s*(?:employees|people|staff|team members)',
                        r'(?:team of|staff of)\s*(\d+)',
                        r'(\d+)\s*(?:engineers|developers)'
                    ]
                    
                    for pattern in size_patterns:
                        match = re.search(pattern, text_lower)
                        if match:
                            size = int(match.group(1))
                            if 1 <= size <= 10000:  # Reasonable company size
                                if size <= 10:
                                    team_info['company_size'] = 'Startup (1-10)'
                                elif size <= 50:
                                    team_info['company_size'] = 'Small (11-50)'
                                elif size <= 200:
                                    team_info['company_size'] = 'Medium (51-200)'
                                else:
                                    team_info['company_size'] = 'Large (200+)'
                                break
                                
            except Exception:
                continue
        
        return team_info
    
    async def _analyze_market_position(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze market positioning and target audience
        
        🧠 CODING THINKING: Why analyze market position?
        1. Helps understand company's business model
        2. Shows target market and customer base
        3. Useful for tailoring outreach approach
        4. Indicates company's growth potential
        """
        
        from server.tools.exa_search import exa_search
        
        company_name = company.get("name", "")
        description = company.get("blurb", "")
        
        # 🧠 CODING THINKING: Why use multiple approaches?
        # 1. Company description gives basic positioning
        # 2. External articles give market perspective
        # 3. Job postings show target customers
        # 4. Multiple sources = more accurate picture
        
        market_info = {}
        
        # Analyze company description
        desc_lower = description.lower()
        
        # Market positioning keywords
        if any(word in desc_lower for word in ['enterprise', 'b2b', 'saas', 'platform']):
            market_info['market_position'] = 'B2B Enterprise'
        elif any(word in desc_lower for word in ['consumer', 'b2c', 'mobile app', 'social']):
            market_info['market_position'] = 'B2C Consumer'
        elif any(word in desc_lower for word in ['developer', 'api', 'tools', 'infrastructure']):
            market_info['market_position'] = 'Developer Tools'
        elif any(word in desc_lower for word in ['ai', 'machine learning', 'data', 'analytics']):
            market_info['market_position'] = 'AI/ML Solutions'
        else:
            market_info['market_position'] = 'Technology Company'
        
        # Look for growth indicators
        growth_queries = [
            f'"{company_name}" growth expanding',
            f'"{company_name}" hiring rapidly',
            f'"{company_name}" new office'
        ]
        
        for query in growth_queries:
            try:
                results = await exa_search(query, num_results=2, want_highlights=True)
                
                for result in results:
                    text = f"{result.get('title', '')} {result.get('summary', '')}"
                    text_lower = text.lower()
                    
                    if any(word in text_lower for word in ['growing', 'expanding', 'hiring', 'scaling']):
                        market_info['growth_indicator'] = 'Growing'
                        break
                        
            except Exception:
                continue
        
        return market_info
    
    async def _analyze_recent_news(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find recent company news and announcements
        
        🧠 CODING THINKING: Why search for recent news?
        1. Shows company is active and growing
        2. Provides talking points for outreach
        3. Indicates company priorities and direction
        4. Helps personalize emails with current events
        """
        
        from server.tools.exa_search import exa_search
        
        company_name = company.get("name", "")
        news_info = {"recent_news": []}
        
        # Reduced queries to save credits - single comprehensive query
        news_queries = [
            f'"{company_name}" news announcement 2024 2025'
        ]
        
        for query in news_queries:
            try:
                results = await exa_search(query, num_results=2, want_highlights=True)  # Reduced from 3 to 2
                
                for result in results:
                    title = result.get("title", "")
                    summary = result.get("summary", "")
                    
                    if title and len(title) > 10:
                        news_info["recent_news"].append(f"{title} - {summary[:100]}")
                        
            except Exception:
                continue
        
        # Limit to top 3 news items
        news_info["recent_news"] = news_info["recent_news"][:3]
        return news_info
    
    async def _analyze_product_roadmap(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find product updates and future plans
        
        🧠 CODING THINKING: Why analyze product roadmap?
        1. Shows company innovation and growth
        2. Provides specific talking points for outreach
        3. Indicates technical challenges they're solving
        4. Helps demonstrate understanding of their work
        """
        
        from server.tools.exa_search import exa_search
        
        company_name = company.get("name", "")
        roadmap_info = {"product_updates": []}
        
        # Search for product updates and roadmap
        roadmap_queries = [
            f'"{company_name}" product roadmap 2024 2025',
            f'"{company_name}" new feature release',
            f'"{company_name}" technology innovation',
            f'"{company_name}" engineering blog'
        ]
        
        for query in roadmap_queries:
            try:
                results = await exa_search(query, num_results=2, want_highlights=True)
                
                for result in results:
                    title = result.get("title", "")
                    summary = result.get("summary", "")
                    
                    if any(word in title.lower() for word in ['launch', 'release', 'feature', 'update', 'innovation']):
                        roadmap_info["product_updates"].append(f"{title} - {summary[:100]}")
                        
            except Exception:
                continue
        
        # Limit to top 2 product updates
        roadmap_info["product_updates"] = roadmap_info["product_updates"][:2]
        return roadmap_info
    
    async def _analyze_culture(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze company culture and values
        
        🧠 CODING THINKING: Why analyze company culture?
        1. Helps assess cultural fit
        2. Provides insights for personalized outreach
        3. Shows company values and priorities
        4. Helps tailor communication style
        """
        
        from server.tools.exa_search import exa_search
        
        company_name = company.get("name", "")
        culture_info = {"company_culture": "Technology-focused company"}
        
        # Search for culture and values
        culture_queries = [
            f'"{company_name}" company culture values',
            f'"{company_name}" team environment',
            f'"{company_name}" remote work policy',
            f'"{company_name}" engineering culture'
        ]
        
        for query in culture_queries:
            try:
                results = await exa_search(query, num_results=2, want_highlights=True)
                
                for result in results:
                    text = f"{result.get('title', '')} {result.get('summary', '')}"
                    text_lower = text.lower()
                    
                    if any(word in text_lower for word in ['culture', 'values', 'team', 'remote', 'collaborative']):
                        culture_info["company_culture"] = text[:200]
                        break
                        
            except Exception:
                continue
        
        return culture_info
    
    async def _analyze_growth_metrics(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Find growth indicators and metrics
        
        🧠 CODING THINKING: Why analyze growth metrics?
        1. Shows company health and trajectory
        2. Indicates hiring needs and opportunities
        3. Provides context for company size and stage
        4. Helps prioritize outreach efforts
        """
        
        from server.tools.exa_search import exa_search
        
        company_name = company.get("name", "")
        growth_info = {"growth_metrics": {}}
        
        # Search for growth indicators
        growth_queries = [
            f'"{company_name}" revenue growth 2024',
            f'"{company_name}" employee count hiring',
            f'"{company_name}" user growth metrics',
            f'"{company_name}" expansion new markets'
        ]
        
        for query in growth_queries:
            try:
                results = await exa_search(query, num_results=2, want_highlights=True)
                
                for result in results:
                    text = f"{result.get('title', '')} {result.get('summary', '')}"
                    text_lower = text.lower()
                    
                    # Look for specific growth indicators
                    if 'revenue' in text_lower and any(word in text_lower for word in ['growth', 'increase', 'million', 'billion']):
                        growth_info["growth_metrics"]["revenue"] = text[:100]
                    elif 'employee' in text_lower and any(word in text_lower for word in ['hiring', 'growing', 'team', 'staff']):
                        growth_info["growth_metrics"]["hiring"] = text[:100]
                    elif 'user' in text_lower and any(word in text_lower for word in ['growth', 'million', 'billion', 'customers']):
                        growth_info["growth_metrics"]["users"] = text[:100]
                        
            except Exception:
                continue
        
        return growth_info
