# Unified Build Plan V2
## Career Readiness Engine — No File Copying Strategy

---

## Your Folder Situation

```
C:\Users\you\
  ├── Agentception - Copy/          ← BIG. Stays here. Never touched.
  │     server/agents/              ← job search agents (rag_companies, job_search, etc.)
  │     server/tools/               ← resume_store, tavily, exa, etc.
  │     server/memory/              ← redis_cache, state_store
  │     server/schemas.py
  │     server/app.py
  │     ui/                         ← old React frontend (ignore)
  │
  ├── agentception-path generator complete/   ← THIS IS WHERE WE BUILD
  │     (ai-learning-path-generator already moved in here)
  │     src/                        ← Flask learning path logic
  │     web_app/                    ← Flask routes (we strip these)
  │     src/data/                   ← role_projects.json, job_market.json, etc.
  │
  └── ai-learning-path-generator/   ← already merged into above, ignore
```

---

## The Core Insight: Path Bridging

Instead of copying files, the new project gets a **bridge config** that tells Python
where to find Agentception's code at runtime.

```python
# agentception-path generator complete/server/bridge.py

import sys
import os

AGENTCEPTION_PATH = os.environ.get(
    "AGENTCEPTION_PATH",
    r"C:\Users\you\Agentception - Copy"   # local default
    # On Railway: set as env var → /app/agentception
)

if AGENTCEPTION_PATH not in sys.path:
    sys.path.insert(0, AGENTCEPTION_PATH)
```

Then anywhere in the new project:

```python
# server/agents/readiness/audit_engine.py

from server.bridge import *          # loads the path
from server.agents.rag_companies import run_rag_company_search   # ← from Agentception - Copy
from server.tools.resume_store import ResumeStore                 # ← from Agentception - Copy
from server.agents.trust_scorer import score_company             # ← from Agentception - Copy
```

**It reads those files directly. Zero duplication.**

---

## Local Development Setup (one-time)

```bash
# In agentception-path generator complete/
# Create .env with the path to the other folder:

AGENTCEPTION_PATH=C:\Users\you\Agentception - Copy
```

```python
# server/bridge.py  — created once, never touched again
import sys, os
from dotenv import load_dotenv
load_dotenv()

agentception_path = os.getenv("AGENTCEPTION_PATH")
if agentception_path and agentception_path not in sys.path:
    sys.path.insert(0, agentception_path)

# Also expose what's available for other devs to see
AGENTCEPTION_MODULES = [
    "server.agents.rag_companies",
    "server.agents.job_search",
    "server.agents.trust_scorer",
    "server.agents.writer_outreach",
    "server.agents.skill_gap_agent",
    "server.tools.resume_store",
    "server.tools.resume_job_matcher",
    "server.tools.tavily_search",
    "server.tools.exa_search",
    "server.memory.redis_cache",
    "server.memory.state_store",
    "server.schemas",
]
```

---

## Railway Deployment Strategy

On Railway, both projects need to be accessible. Two options:

**Option A — Monorepo (recommended)**
```
your-github-repo/
  agentception/          ← push Agentception - Copy here (rename, gitignore heavy files)
  app/                   ← push agentception-path generator complete here
  railway.toml           ← points to app/ as the service root
```

```toml
# railway.toml
[build]
builder = "nixpacks"
buildCommand = "pip install -r app/requirements.txt"

[deploy]
startCommand = "cd app && uvicorn server.app:app --host 0.0.0.0 --port $PORT"

[env]
AGENTCEPTION_PATH = "/app/../agentception"
```

**Option B — Symlink at build time (simpler)**
```dockerfile
# Dockerfile in agentception-path generator complete/
FROM python:3.11-slim
WORKDIR /workspace

# Copy both projects
COPY ./agentception /workspace/agentception
COPY ./app /workspace/app

ENV AGENTCEPTION_PATH=/workspace/agentception

WORKDIR /workspace/app
RUN pip install -r requirements.txt
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Full Awareness Map

This is what the new project can see and use from Agentception - Copy
via the bridge. Nothing copied. Just referenced.

### Job Search Agents (read via bridge)
```
rag_companies.py          → run_rag_company_search()   ← scrapes 20 live JDs
job_search.py             → ALLOWED_JOB_DOMAINS        ← 86 approved job boards
trust_scorer.py           → score_company()            ← trust 0-100
writer_outreach.py        → write_emails_incremental() ← personalized emails
skill_gap_agent.py        → analyze_gaps()             ← existing gap logic
focused_research_agent.py → research_company()         ← company intel
```

### Tools (read via bridge)
```
resume_store.py           → ResumeStore                ← resume parsing + storage
resume_job_matcher.py     → compute_match_score()      ← resume vs JD score
tavily_search.py          → TavilySearch               ← primary search
exa_search.py             → ExaSearch                  ← neural search
http_fetch.py             → fetch_url()                ← generic fetcher
geocode.py                → geocode_location()         ← maps
resume_pdf_generator.py   → generate_pdf()             ← PDF export
```

### Memory (read via bridge)
```
redis_cache.py            → RedisCache                 ← caching layer
state_store.py            → Memory, TimelineBus        ← SSE + in-memory KV
sql_store.py              → SQLStore                   ← SQLite CRUD
```

### Schemas (read via bridge)
```
schemas.py                → CompanyIntel, HiringCompany, JobPosting,
                            TimelineEvent, all Pydantic models
```

### Data files that STAY in ai-learning-path-generator (already in new project)
```
src/data/role_projects.json    ← portfolio project ideas per role
src/data/role_resources.json   ← learning resources per role
src/data/job_market.json       ← 12 career pillars, salaries, companies
src/data/gold_resources.json   ← curated top resources
src/ml/job_market.py           ← JobMarketAnalyzer (Perplexity)
src/ml/resource_search.py      ← ResourceSearchEngine
src/learning_path.py           ← LearningPathGenerator
src/utils/perplexity.py        ← Perplexity client
src/utils/observability.py     ← LangSmith + W&B tracing
```

---

## New Files to Create (only in agentception-path generator complete)

These are the only files you write from scratch.
Everything else is imported via bridge.

```
server/
  bridge.py                          ← path bridge (10 lines)
  agents/
    readiness/
      audit_engine.py                ← CORE: orchestrates the audit
      decision_engine.py             ← maps audit gap → one action
      verdict_loop.py                ← logs + analyzes outcomes
      cohort_analytics.py            ← peer patterns (after 50 users)
      one_thing/
        reframe_bullets.py           ← rewrites undefendable resume bullets
        learning_module_generator.py ← 2-week module from existing JSON data
  workers/
    readiness_tasks.py               ← RQ background tasks for audit
  data/
    audit_prompts.py                 ← all prompt templates

tools/
  kimi_client.py                     ← Kimi API wrapper (~30 lines)
  exa_portfolio_search.py            ← Exa calls for portfolio benchmarking

app.py (modifications only)          ← add 4 new routes, import bridge at top

ui/src/pages/
  Audit.tsx                          ← new main entry point
  OneThing.tsx                       ← action display
  VerdictLoop.tsx                    ← outcomes + pattern view

ui/src/components/
  VerdictCard.tsx
  OutcomeTimeline.tsx
  GapBadge.tsx

alembic/versions/
  002_readiness_tables.py            ← 3 new tables
```

**Total new files: ~15 backend, ~5 frontend.**
Everything else: imported from the other folder.

---

## Database: 3 New Tables

Add to existing Postgres (Supabase) via Alembic. Existing tables untouched.

```sql
-- Stores each audit run
CREATE TABLE readiness_audits (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID REFERENCES users(id),
  target_role   TEXT NOT NULL,
  resume_token  TEXT,
  jd_count      INTEGER,
  verdict_text  TEXT,
  gap_type      TEXT CHECK (gap_type IN ('skills', 'framing', 'ready')),
  gap_details   JSONB,
  percentile    INTEGER,
  created_at    TIMESTAMPTZ DEFAULT now()
);

-- Stores the one action generated from audit
CREATE TABLE one_thing_actions (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_id     UUID REFERENCES readiness_audits(id),
  action_type  TEXT CHECK (action_type IN ('learn_module', 'reframe_bullet', 'apply_now')),
  action_data  JSONB,
  deadline_days INTEGER,
  completed    BOOLEAN DEFAULT false,
  completed_at TIMESTAMPTZ
);

-- Stores application outcomes (the feedback loop)
CREATE TABLE application_outcomes (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id           UUID REFERENCES users(id),
  audit_id          UUID REFERENCES readiness_audits(id),
  company           TEXT,
  role              TEXT,
  applied_at        TIMESTAMPTZ,
  outcome           TEXT CHECK (outcome IN ('ghosted','rejected','screen','onsite','offer')),
  outcome_logged_at TIMESTAMPTZ
);
```

---

## API: 4 New Routes (added to existing app.py)

```python
# All added to server/app.py
# Import bridge at the very top of app.py:
import server.bridge   # ← this one line gives access to all Agentception modules

POST /audit/start
    → starts background RQ job → returns run_id
    → SSE via existing /timeline/{run_id} (reuse unchanged)

GET  /audit/{run_id}/result
    → returns verdict_text, gap_type, gap_details, percentile

POST /audit/{audit_id}/one-thing
    → triggers decision_engine → returns action

POST /outcomes/log
    → logs application outcome (company, role, result)

GET  /outcomes/patterns
    → returns verdict_loop insight for the user
```

---

## Phase Plan (12 weeks, realistic)

### Phase 0 — Bridge + Foundation (Week 1)
```
Day 1-2:
  - Create server/bridge.py
  - Add AGENTCEPTION_PATH to .env
  - Test: python -c "import server.bridge; from server.agents.rag_companies import run_rag_company_search; print('ok')"
  - If that prints 'ok', Phase 0 is done

Day 3-4:
  - Create 002_readiness_tables.py Alembic migration
  - alembic upgrade head
  - Verify 3 new tables exist in Postgres

Day 5:
  - Deploy to Railway with AGENTCEPTION_PATH env var set
  - Confirm /health returns 200
```

**Done when**: Both projects talk to each other. Tables exist. Railway deploys.

---

### Phase 1 — The Audit (Week 2-4)
```
audit_engine.py flow:
  1. run_rag_company_search() ← from Agentception via bridge (scrapes 20 JDs)
  2. exa_portfolio_search()   ← new: finds real engineer portfolios for benchmarking
  3. JobMarketAnalyzer()      ← from learning path (Perplexity live market signal)
  4. kimi_client.analyze()    ← new: sends [resume + 20 JDs] in one call
  5. gpt4o_verdict()          ← new: converts JSON → honest paragraph
  6. store in readiness_audits table
  7. emit SSE via existing TimelineBus (unchanged)
```

**Kimi prompt** (in audit_prompts.py):
```python
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
```

**Frontend Audit.tsx**:
- Resume upload (reuse existing upload component)
- Role picker (reuse existing role list from roles.py)
- SSE progress bar (reuse existing Timeline.tsx)
- Verdict display: 3 sections — Where you stand / What's blocking / Your strengths

---

### Phase 2 — The One Thing (Week 5-6)
```
decision_engine.py:

  gap_type == "ready"    → writer_outreach.py (from Agentception) generates emails
                           for top 5 matching companies from rag results

  gap_type == "framing"  → reframe_bullets.py rewrites undefendable claims
                           using GPT-4o with specific JD evidence

  gap_type == "skills"   → learning_module_generator.py pulls from:
                             - role_projects.json (pick project for the gap skill)
                             - role_resources.json (pick 3 resources)
                             - DeepSeek generates 14-day daily plan
                           Output: 1 project + 3 resources + daily breakdown
                           Max deadline: 14 days. No 12-week plans.
```

**Frontend OneThing.tsx**:
- "Ready": 5 job cards + generated emails (existing JobCard.tsx reused)
- "Framing": side-by-side bullet rewrite (original / suggested)
- "Skills": 14-day plan with checkbox per day + countdown timer

---

### Phase 3 — Verdict Loop (Week 7-9)
```
verdict_loop.py:
  - Reads application_outcomes for user
  - Reads their readiness_audit for context
  - Requires min 5 outcomes before showing patterns
  - After 50 users: ChromaDB similarity search for peer comparison
    (only shown when n≥10 for same role + gap_type)

cohort_analytics.py:
  - Embeds audit verdict_text → store in ChromaDB
  - On each outcome log → update ChromaDB record
  - Query: "students with similar audit in same role who logged outcomes"
  - Surface: "Your callback rate vs similar profiles"
```

**Frontend VerdictLoop.tsx**:
- Timeline dots: each application → outcome color (gray=ghosted, yellow=screen, green=offer)
- One insight paragraph from pattern detector
- Peer comparison only when data exists

---

### Phase 4 — Deploy + Security (Week 10-12)

**Security (non-negotiable before real users)**:
```python
# Add to every route that touches user data:
user_id: str = Depends(verify_jwt)

# Resume token: 15-min expiry
def create_resume_token(user_id, resume_id):
    return jwt.encode(
        {"user_id": user_id, "resume_id": resume_id, "exp": time() + 900},
        RESUME_TOKEN_SECRET
    )

# Input sanitization:
class AuditRequest(BaseModel):
    target_role: constr(max_length=100, pattern=r"^[a-zA-Z0-9 ,.\-/]+$")
    resume_token: Optional[str]
```

**Railway .env vars needed**:
```
AGENTCEPTION_PATH=/workspace/agentception   ← path to Agentception - Copy on Railway
OPENAI_API_KEY=
KIMI_API_KEY=                               ← from platform.moonshot.cn
PERPLEXITY_API_KEY=
EXA_API_KEY=
TAVILY_API_KEY=
DEEPSEEK_API_KEY=
REDIS_URL=
DATABASE_URL=
SUPABASE_JWT_SECRET=
RESUME_TOKEN_SECRET=
```

**Vercel .env vars needed**:
```
NEXT_PUBLIC_API_URL=https://your-app.railway.app
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
```

---

## Week 1 Exact Steps (Start Here)

```bash
# Step 1: verify the bridge works locally
cd "agentception-path generator complete"

# Create .env
echo 'AGENTCEPTION_PATH=C:\Users\you\Agentception - Copy' >> .env

# Create bridge.py
cat > server/bridge.py << 'EOF'
import sys, os
from dotenv import load_dotenv
load_dotenv()

path = os.getenv("AGENTCEPTION_PATH")
if path and path not in sys.path:
    sys.path.insert(0, path)
EOF

# Step 2: test it
python -c "
import server.bridge
from server.agents.rag_companies import run_rag_company_search
from server.tools.resume_store import ResumeStore
print('Bridge works. Both projects connected.')
"

# Step 3: create Alembic migration
alembic revision --autogenerate -m "readiness_tables"
# edit the file to add the 3 tables from the schema above
alembic upgrade head

# Step 4: verify tables
python -c "from server.memory.sql_store import SQLStore; print('DB ok')"

# Step 5: start FastAPI
uvicorn server.app:app --reload --port 8000
# navigate to localhost:8000/health → should return 200
```

If Step 2 prints "Bridge works", you're ready to build `audit_engine.py`.

---

## What NOT to Do

- Do not copy any file from `Agentception - Copy` into the new project
- Do not run both backends simultaneously — one FastAPI backend, bridge handles access
- Do not modify any file in `Agentception - Copy` — treat it as read-only external library
- Do not add Flask to the new project — strip Flask imports when using learning path modules

---

*V2 — no file copying, bridge-based module sharing*
*Both projects stay in their folders. Railway gets both via monorepo or Docker COPY.*
