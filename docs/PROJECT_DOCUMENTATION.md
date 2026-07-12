# Agentception - Complete Project Documentation

## Quick Reference (For LLM Context)

### Entry Points
- **Backend API**: `server/app.py` - FastAPI application with all endpoints
- **Frontend App**: `ui/src/App.tsx` - React app with routing
- **Main Search Endpoint**: `POST /rag/companies` - Core job search functionality
- **Load More Endpoint**: `POST /rag/companies/load-more` - Instant cached results
- **Frontend Main Page**: `ui/src/pages/Index.tsx` - Primary user interface

### Critical Files (Top 8)
1. `server/app.py` - All API endpoints, request/response handling
2. `server/agents/rag_companies.py` - Core search orchestration with location filtering
3. `server/agents/job_search.py` - Job search engine with ATS URL parsing
4. `server/schemas.py` - All data models and type definitions
5. `ui/src/pages/Index.tsx` - Main UI component for job search
6. `server/memory/state_store.py` - In-memory caching for Load More functionality
7. `.env` - API keys configuration (Tavily, DeepSeek, Google Maps)
8. `docs/job-search-engineering.md` - Detailed technical documentation

### Environment Variables Required
```
TAVILY_API_KEY=xxx          # Primary search API
PERPLEXITY_API_KEY=xxx      # Enhanced research
EXA_API_KEY=xxx            # Alternative search
GOOGLE_MAPS_KEY=xxx        # Location geocoding
DEEPSEEK_API_KEY=xxx       # LLM for email generation
MOCK_SEARCH=false          # Set to true for testing
REDIS_URL=rediss://...     # Redis Cloud for caching (optional)
TAVILY_DISABLE_SSL_VERIFY=true  # Fix for SSL issues
```

---

## Architecture Overview

### High-Level Data Flow
```
User Input (Location, Role) 
    ↓
Frontend (React/Vite @ :8080)
    ↓ (API call)
Backend (FastAPI @ :8000)
    ↓
RAG Agent → Job Search → Enhanced Research → Writer Agent
    ↓
Results stored in Memory/SQLite
    ↓
Frontend displays results via SSE
```

### Technology Stack
- **Backend**: Python 3.11, FastAPI, Uvicorn, SQLite
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Search APIs**: Tavily (primary), Exa.ai (backup)
- **LLM**: DeepSeek for email generation
- **State Management**: In-memory with SQLite persistence

---

## Detailed File Structure

### Backend (`/server`)

#### Core Application
- **`app.py`** (51KB) - Main FastAPI application
  - 18 API endpoints
  - CORS configuration
  - Background task handling
  - SSE streaming for real-time updates
  
- **`schemas.py`** (12KB) - Pydantic data models
  - `CompanyIntel` - Company information structure
  - `TimelineEvent` - Real-time update messages
  - `JobPosting` - Job posting details
  - Request/Response models for all endpoints

#### Agent System (`/agents`)
- **`rag_companies.py`** (3.0KB) - Main search orchestrator
  - `find_companies_for_role()` - Core job search with location filtering
  - `direct_ats_search()` - Parallel ATS search (Lever, Greenhouse, Ashby)
  - `extract_company_and_title()` - Enhanced ATS URL parsing
  - `format_job_for_display()` - Job data normalization
  - Location abbreviation expansion (la → Los Angeles, CA)
  - ATS URL filtering (prevents StackOverflow results)
  - Load More caching functionality
  
- **`job_search.py`** (2.5KB) - Legacy job search engine
  - `ALLOWED_JOB_DOMAINS` - 86 approved job boards/ATS
  - `extract_company_from_ats_url()` - Enhanced ATS URL parsing
  - Job parsing and normalization
  - LLM-based result processing
  - Location-aware filtering
  
- **`enhanced_research_agent.py`** - Company intelligence gathering
  - Fetches recent news, tech stack, funding info
  - Parallel processing with fault tolerance
  
- **`writer_outreach.py`** - Email generation
  - Uses DeepSeek LLM
  - Personalizes content with research + resume
  
- **`match.py`** - Semantic matching algorithm
  - Embedding-based similarity search
  - Company scoring and ranking

#### Memory Management (`/memory`)
- **`state_store.py`** - In-memory state management
  - `Memory` class for caching
  - `TimelineBus` for SSE streaming
  
- **`sql_store.py`** - SQLite persistence
  - Save/load functionality
  - Long-term storage
  
- **`redis_cache.py`** - Redis Cloud integration
  - Fallback to in-memory if Redis unavailable
  - SSL connection handling for Redis Cloud
  - Production-ready caching

#### RAG System (`/rag`)
- **`roles.py`** - Role definitions and keywords
  - 20+ predefined roles (AI Engineer, Data Scientist, etc.)
  - Associated search terms and value propositions

#### Tools (`/tools`)
- **`http_fetch.py`** - HTTP client for web scraping
- **`resume_store.py`** - Resume processing and storage
- **`resume_job_matcher.py`** - Resume-job compatibility scoring
- **`resume_pdf_generator.py`** - PDF generation from templates

#### Templates (`/templates`)
- 6 resume templates in HTML/CSS format
- Used for PDF generation

### Frontend (`/ui`)

#### Main Application
- **`App.tsx`** - React app with routing
  - React Router setup
  - QueryClient for API state management
  - Toast notifications

#### Pages (`/pages`)
- **`Index.tsx`** (16KB) - Main job search interface
  - Location/role input form
  - Resume upload
  - Results display with timeline
  - Real-time SSE updates
  
- **`TailorResume.tsx`** (19KB) - Resume tailoring feature
  - Supabase integration
  - Job description parsing
  - ATS score calculation

#### Components (`/components`)
- **`ui/`** - Reusable UI components (Button, Input, Card, etc.)
- **`LiquidBackground.tsx`** - Animated gradient background
- **`Timeline.tsx`** - Real-time progress display
- **`ResultsGrid.tsx`** - Company results display

#### Configuration
- **`vite.config.ts`** - Vite configuration
  - Proxy setup: `/api` → `http://localhost:8000`
  - Path aliases (`@/` → `./src`)

---

## API Endpoints

### Core Search & Discovery
- `POST /rag/companies` - Main job search endpoint
  ```python
  request: {
    city: str,
    role: str,
    resumeToken?: str,
    depth?: str,
    filters?: SearchFilters
  }
  response: { run_id: str }
  ```

- `POST /rag/companies/load-more` - Load cached results instantly
  ```python
  request: {
    run_id: str,
    offset: int = 5,
    limit: int = 5
  }
  response: {
    companies: List[dict],
    has_more: bool,
    total_cached: int
  }
  ```

- `POST /rag/companies/load-more-roles` - Expand search with more roles
- `POST /writer/outreach` - Generate personalized emails

### Resume & Job Processing
- `POST /upload/resume` - Upload and parse PDF resume
- `POST /api/compute-match-score` - Calculate resume-job compatibility
- `POST /api/fetch-job-description` - Parse job description from URL
- `POST /api/tailor-resume-from-job` - Tailor resume to specific job

### Results & State
- `GET /results/{run_id}` - Retrieve search results
- `GET /timeline/{run_id}` - SSE stream for real-time updates
- `POST /save/add` - Save companies/results
- `GET /save/list` - Retrieve saved items

### Utilities
- `GET /health` - Health check
- `GET /api/templates` - List resume templates
- `POST /api/generate-pdf` - Generate PDF from template

### Debug Endpoints
- `GET /debug/pdf` - Check PDF library availability
- `GET /debug/tavily` - Test Tavily API
- `GET /debug/memory/{run_id}` - Inspect memory state

---

## Agent Workflow Details

### 1. RAG Agent (rag_companies.py)
```python
async def run_rag_company_search(
    run_id: str,
    city: str,
    role: str,
    resume_token?: str,
    filters?: dict,
    emit: Callable
)
```
**Process:**
1. Extract role from resume if not provided
2. **Phase 0**: Direct ATS search with location filtering
   - Parallel search on Lever, Greenhouse, AshbyHQ
   - Location matching (city/state) + Remote fallback
   - Cache extra results for Load More
3. Phase 1: Discover additional companies (supplementary)
4. Enrich companies with research data
5. Store in memory for downstream agents

**Performance**: 5 results in 3-5 seconds (vs 30-60s before)

### 2. Enhanced Research Agent
**Process:**
1. For each discovered company:
   - Fetch recent news (last 30 days)
   - Identify tech stack from job descriptions
   - Get funding information
   - Analyze growth metrics
2. Parallel processing with rate limiting
3. Cache results to minimize API calls

### 3. Writer Agent
**Process:**
1. Combine company research with resume insights
2. Generate personalized email using DeepSeek
3. Include specific hooks based on company data
4. Format with subject and mailto link

---

## Key Data Models

### CompanyIntel
```python
{
    "name": str,
    "homepage": str,
    "source_url": str,
    "blurb": str,
    "city": str,
    "tags": List[str],
    "contact_hint": str,
    "score": float
}
```

### HiringCompany
```python
{
    "company_name": str,
    "homepage_url": str,
    "job_title": Optional[str],
    "job_url": Optional[str],
    "job_location": Optional[str],  # Includes location tags (📍/🌐)
    "score": float,
    "rank_score": float,
    "tags": List[str],
    "resume_match_score": Optional[float],
    "job_posting": JobPosting,  # Nested job details
    "display_data": dict,       # Cleaned display fields
    "trust_score": int,         # Trust scoring (0-100)
    "is_expired": bool
}
```

### JobPosting
```python
{
    "url": str,
    "title": str,
    "snippet": str,
    "location": str,
    "company": str,
    "source": str,
    "is_ats": bool,
    "is_listing": bool,
    "score": float
}
```

### TimelineEvent
```python
{
    "run_id": str,
    "agent": str,
    "message": str,
    "level": str,  # "info", "warn", "error"
    "timestamp": datetime
}
```

---

## Search Algorithm Details

### Parallel ATS Search (Dec 2025 Update)
- **3 parallel searches**: Lever, Greenhouse, AshbyHQ
- **Location-aware queries**: `"role" "location" jobs`
- **Smart filtering**: Word boundary matching for company names
- **Score boosting**: +30 for local, +10 for remote
- **Deduplication**: By URL and company name
- **ATS URL filtering**: Only process URLs from known ATS platforms
- **Lever URL support**: Handles both `jobs.lever.co/company/` and `company.lever.co/` patterns

### Location Filtering
- Parses "Austin, TX" → city + state
- Maps state abbreviations (TX → Texas)
- Identifies remote jobs (remote, wfh, anywhere)
- Prioritizes: Local > Remote > Other
- **Location abbreviation expansion**: la → Los Angeles, CA
- **Context-aware matching**: Remote vs local query handling

### Caching System
- **Load More cache**: `loadmore:{run_id}` key
- **Redis Cloud integration**: Production-ready caching
- **Fallback to in-memory**: If Redis unavailable
- **SSL connection handling**: For Redis Cloud
- Stores extra results beyond first 5
- Instant retrieval (<100ms)
- No additional API calls needed

### Role-Based Site Optimization
- Each role maps to 2-3 optimal job boards
- Example: "AI Engineer" → YC Jobs, BuiltIn SF, Wellfound
- Reduces noise and improves relevance

### Domain Filtering
- 86 approved domains in `ALLOWED_JOB_DOMAINS`
- Filters out low-quality job boards
- Focus on ATS systems and premium boards

### Semantic Matching
- Uses embeddings for similarity scoring
- Combines keyword and semantic search
- Ranks companies by relevance to role/resume

---

## Development Notes

### Running the Project
```bash
# Backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# Frontend (new terminal)
cd ui
npm install
npm run dev
```

### Testing
- Mock mode available: Set `MOCK_SEARCH=true` in `.env`
- Debug endpoints for API validation
- Comprehensive logging throughout

### Performance Optimizations
- **Parallel ATS search**: 3x faster (3-5s vs 30-60s)
- **In-memory caching**: Load More in <100ms
- **Location filtering**: Reduces irrelevant results
- **Error handling**: Comprehensive try/catch with logging
- **Rate limiting**: For external APIs
- **Lazy loading**: In frontend

### Recent Improvements (Dec 2025)
1. **Fast Parallel Search**: 3 ATS platforms simultaneously
2. **Location-Aware Filtering**: City/state matching + remote
3. **Load More Caching**: Instant pagination without API calls
4. **Enhanced ATS Parsing**: Support for Workday, Workable
5. **Word Boundary Validation**: Better company name filtering
6. **Error Handling**: Background task crash detection
7. **Redis Cloud Integration**: Production-ready caching
8. **Lever URL Fix**: Support for jobs.lever.co/company pattern
9. **Location Abbreviation Expansion**: la → Los Angeles, CA
10. **ATS URL Filtering**: Prevents non-job URLs (StackOverflow)

### Known Issues
- Duplicate route warnings (harmless)
- PDF library compatibility checks in debug endpoints
- Supabase integration separate from main search flow
- **Location matching bugs**: Remote jobs sometimes marked as local
- **Redirect issues**: Some job URLs redirect to wrong locations
- **Data quality**: Search API returns irrelevant URLs (StackOverflow)

---

## Future Enhancement Points
1. **Two-Stage Pipeline**: Fast initial results + background deep scraping
2. **LLM-Powered Extraction**: Replace regex with LLM for company/title parsing
3. **Job-Specific APIs**: Integrate Apify/LinkedIn for better data quality
4. **Context-Aware Location**: Fix remote vs local matching logic
5. **URL Validation**: Detect redirects before showing results
6. **Real-time Result Streaming**: Progressive loading
7. **User Authentication**: Saved searches and preferences
8. **More Job Board Integrations**: LinkedIn, Indeed APIs
9. **Advanced Filters**: Salary range, company size, industry
10. **Application Tracking**: Track applied jobs and responses

## Current Status (Dec 2025)
- ✅ Parallel ATS search implemented
- ✅ Location filtering working
- ✅ Load More caching functional
- ✅ Redis Cloud integration
- ✅ Lever URL parsing fixed
- ✅ ATS URL filtering implemented
- ✅ Location abbreviation expansion
- 🔄 Supabase resume tailoring (paused - DB setup needed)
- 🔄 Location matching logic (needs context-aware fix)
- 📋 Next: LLM-powered entity extraction

---

## Dependencies Graph

### Backend Dependencies
```
fastapi → uvicorn (server)
pydantic → data validation
httpx → async HTTP client
python-multipart → file uploads
python-dotenv → env variables
PyMuPDF/pypdf/pdfplumber → PDF parsing
redis → Redis Cloud caching (optional)
```

### Frontend Dependencies
```
react → UI framework
vite → build tool
tailwindcss → styling
@tanstack/react-query → API state
react-router-dom → routing
framer-motion → animations
```

---

## Supabase Integration Status (Paused)

### Resume Tailoring System
- **Location**: `ui/supabase/` folder
- **Components**:
  - `parse-resume` - Edge function for resume parsing
  - `parse-job-description` - Job description extraction
  - `tailor-resume` - Resume customization
  - `calculate-ats-score` - ATS optimization scoring

### Current Blocker
- Missing `public.resumes` table in Supabase DB
- Fix: Apply `ui/supabase/migrations/001_initial_schema.sql`
- Status: User paused to focus on job search improvements

---

*Last Updated: December 2025*
*Version: 1.3.0*
*Recent Updates: Redis Cloud integration, Lever URL parsing, ATS filtering, Location expansion*
