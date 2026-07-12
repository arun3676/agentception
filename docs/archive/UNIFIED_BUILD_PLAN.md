# Unified Build Plan: Career Readiness Engine

> One product. Two codebases merged. One real problem solved.
> **The problem**: Students don't know if they're ready to apply, what's blocking them,
> or whether studying more vs applying more is the right move right now.

---

## The Core Idea (say it in one sentence)

> "Upload your resume, tell us your target role — we'll tell you honestly if you're ready,
> what's blocking you, and give you ONE specific thing to do about it."

Not a score. Not a 12-week plan. A decision with reasoning.

---

## How the Two Codebases Connect

This is the creative connection — neither codebase gets erased.
They become two **agent clusters** inside one FastAPI backend.

```
Flask learning path app → ported as: learning_agents/ cluster
FastAPI job search app  → stays as:  search_agents/ cluster

New layer on top of both: readiness_orchestrator/
  → calls both clusters
  → is the actual product
```

The Flask app's `LearningPathGenerator`, `JobMarketAnalyzer`, `ResourceSearchEngine`,
`skill_gap_agent`, and all the JSON data files (`role_projects.json`, `role_resources.json`,
`job_market.json`) get imported directly into the FastAPI project as Python modules.

No rewrite. Just move the files, update imports, drop Flask-specific code.

---

## What Each API Does Specifically

| API | Exact role | Where called |
|---|---|---|
| **Exa** | Neural search for "engineers hired at [company] + their actual GitHub/portfolio" | audit_engine.py — finds real proof examples to benchmark against |
| **Tavily** | Scrape live JDs from Lever/Greenhouse/Ashby | rag_companies.py — already works, unchanged |
| **Perplexity** | "What is the hiring bar for [role] at [company type] right now, May 2026?" | audit_engine.py — live market context, replaces stale job_market.json |
| **Kimi (1M context)** | Read 20 full JDs + full resume in ONE prompt → holistic analysis | audit_engine.py — the core audit call, avoids chunking errors |
| **DeepSeek** | Fast reasoning for "one thing" recommendation, email generation | decision_engine.py, writer_outreach.py |
| **GPT-4o** | The brutal honest verdict paragraph — highest quality, used once | audit_engine.py — the output the user reads |
| **ChromaDB** | Store audit→outcome pairs, find similar student profiles | verdict_loop.py — the compounding moat |

---

## Three User Moments (the whole product)

```
MOMENT 1 — THE AUDIT (day 1)
  Upload resume + pick target role
  → System scrapes 20 real JDs (Tavily/Exa)
  → Kimi reads everything at once
  → GPT-4o writes honest verdict
  Output: "Here's where you stand. Here's what's actually blocking you."

MOMENT 2 — THE ONE THING (day 1, same session)
  Based on the audit gap type:
  If gap = skills missing   → DeepSeek generates 2-week focused module
                              (from role_projects.json + role_resources.json)
  If gap = resume framing   → rewrite specific bullets with examples
  If gap = ready to apply   → writer_outreach.py fires, generates emails
  Output: ONE specific action with a deadline, not a 12-week plan

MOMENT 3 — THE VERDICT LOOP (week 2+)
  User logs outcomes (1 click: ghosted / screen / rejected / offer)
  ChromaDB stores audit + outcome pair
  After 4-6 weeks: "Here's what your data is showing.
  You applied to 12 roles, 0 callbacks. The audit said X was your gap.
  You haven't closed it. Here's evidence it's the actual blocker."
  Output: Honest pattern recognition that builds trust
```

---

## File Map: What Moves Where

### From Flask app → FastAPI project

```
src/learning_path.py          → server/agents/learning/path_generator.py
src/ml/job_market.py          → server/agents/learning/job_market_analyzer.py
src/ml/resource_search.py     → server/agents/learning/resource_search.py
src/data/role_projects.json   → server/data/role_projects.json
src/data/role_resources.json  → server/data/role_resources.json
src/data/job_market.json      → server/data/job_market.json
src/data/gold_resources.json  → server/data/gold_resources.json
src/utils/perplexity.py       → server/tools/perplexity.py
src/utils/observability.py    → server/tools/observability.py
worker/tasks.py               → server/workers/tasks.py (adapt from RQ → same RQ, already in FastAPI)
```

### Stays in FastAPI (unchanged)

```
server/agents/rag_companies.py      ← job scraping, untouched
server/agents/job_search.py         ← JD parsing, untouched
server/agents/trust_scorer.py       ← untouched
server/tools/resume_store.py        ← untouched
server/tools/resume_job_matcher.py  ← feeds into audit
server/memory/redis_cache.py        ← untouched
server/memory/state_store.py        ← untouched
```

### New files (the orchestration layer)

```
server/agents/readiness/
  audit_engine.py          ← CORE: scrape JDs + Kimi analysis + GPT-4o verdict
  decision_engine.py       ← maps audit gap → one action (learn / reframe / apply)
  verdict_loop.py          ← logs outcomes, queries ChromaDB, surfaces patterns
  cohort_analytics.py      ← anonymous peer comparison (n≥10 guard)

server/tools/
  kimi_client.py           ← Kimi API wrapper (Moonshot AI, OpenAI-compatible)
  exa_portfolio_search.py  ← Exa calls for finding real engineer portfolios

server/data/
  audit_prompts.py         ← all prompt templates in one place

ui/src/pages/
  Audit.tsx                ← the new main entry point
  OneThing.tsx             ← action display + learning module
  VerdictLoop.tsx          ← outcomes log + pattern view (replaces Applications.tsx)
```

---

## Database Schema Changes

### New tables (add to existing Postgres via Alembic)

```sql
-- stores each readiness audit
CREATE TABLE readiness_audits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  target_role TEXT NOT NULL,
  resume_token TEXT,
  jd_count INTEGER,
  verdict_text TEXT,           -- the GPT-4o paragraph
  gap_type TEXT,               -- 'skills' | 'framing' | 'ready'
  gap_details JSONB,           -- specific gaps with evidence
  readiness_percentile INTEGER,
  created_at TIMESTAMPTZ DEFAULT now(),
  embedding VECTOR(1536)       -- pgvector for ChromaDB-style similarity
);

-- stores one-thing actions
CREATE TABLE one_thing_actions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  audit_id UUID REFERENCES readiness_audits(id),
  action_type TEXT,            -- 'learn_module' | 'reframe_bullet' | 'apply_now'
  action_data JSONB,           -- the specific content
  deadline_days INTEGER,
  completed BOOLEAN DEFAULT false,
  completed_at TIMESTAMPTZ
);

-- stores application outcomes
CREATE TABLE application_outcomes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  audit_id UUID REFERENCES readiness_audits(id),
  company TEXT,
  role TEXT,
  applied_at TIMESTAMPTZ,
  outcome TEXT,                -- 'ghosted' | 'rejected' | 'screen' | 'onsite' | 'offer'
  outcome_logged_at TIMESTAMPTZ,
  days_to_outcome INTEGER
);
```

---

## Phase Plan

### Phase 0 — Foundation (Week 1-2)
**Goal**: One running FastAPI backend. Both codebases merged. Nothing broken.

**Tasks**:
1. Copy Flask `src/` modules into `server/agents/learning/`. Update imports, remove Flask decorators.
2. Copy all JSON data files into `server/data/`.
3. Add `kimi_client.py` (Kimi uses OpenAI-compatible API — 10 lines).
4. Add Alembic migration for 3 new tables.
5. Wire Supabase auth JWT middleware into FastAPI (already partially done).
6. Deploy skeleton to Railway. Confirm `/health` returns 200.

**What you can show after Phase 0**: One backend URL. Both old pages still work. Nothing new, nothing broken.

**Files to create/modify**:
```
server/agents/learning/          ← new folder, copy from Flask src/
server/tools/kimi_client.py      ← new, ~30 lines
server/tools/perplexity.py       ← copy from Flask utils/
server/data/                     ← copy all JSON files
alembic/versions/002_readiness.py ← new migration
```

---

### Phase 1 — The Audit (Week 3-5)
**Goal**: Core product works end-to-end. Student can get a verdict.

**The flow**:
```
POST /audit/start
  → background task starts
  → SSE stream to frontend

Background task:
  1. rag_companies.py scrapes 20 JDs (existing, unchanged)
  2. Exa searches for "engineers hired at [role] + [company type] portfolio"
  3. Perplexity fetches live market signal
  4. Kimi: send [resume + 20 JDs + market signal] in one 100k token prompt
     → returns structured JSON: {gaps: [], strengths: [], evidence: {}}
  5. GPT-4o: convert JSON → honest paragraph verdict
  6. Store in readiness_audits table + ChromaDB
  7. Emit SSE event → frontend updates
```

**Key prompt for Kimi** (goes in `audit_prompts.py`):
```
You are a brutally honest career advisor reviewing a student's resume
against real job descriptions.

<RESUME>{resume_text}</RESUME>

<JOB_DESCRIPTIONS>
{jd_1}
---
{jd_2}
... (all 20)
</JOB_DESCRIPTIONS>

<MARKET_SIGNAL>{perplexity_output}</MARKET_SIGNAL>

Tasks:
1. Count how many JDs mention each skill/requirement.
2. For each requirement mentioned in 50%+ of JDs, check if resume shows evidence.
3. Flag resume claims the student may struggle to defend in an interview.
4. Identify 2-3 genuine strengths (where student is above average vs JDs).
5. Give a percentile estimate (rough, honest).

Return ONLY valid JSON:
{
  "gaps": [{"skill": str, "jd_frequency": int, "resume_evidence": str|null}],
  "undefendable_claims": [{"bullet": str, "reason": str}],
  "strengths": [{"skill": str, "evidence": str}],
  "percentile_estimate": int,
  "gap_type": "skills"|"framing"|"ready"
}
```

**Key prompt for GPT-4o** (converts JSON → verdict):
```
Convert this structured audit into 2-3 paragraphs of honest, direct career advice.
Tone: like a mentor who respects the person enough to tell the truth.
No fluff. No "great job!" No "you're almost there!"
Be specific — name the actual gaps, name the actual strengths.
If they're ready, say so clearly and tell them which companies to hit first.
If they're not ready, tell them exactly what the exit condition is.

{audit_json}
```

**Frontend** (`Audit.tsx`):
- Clean input: resume upload + role picker (from existing role list)
- SSE progress bar while audit runs (reuse `Timeline.tsx` component)
- Verdict display: 3 sections — "Where you stand" / "What's blocking you" / "Your strengths"

**Files to create**:
```
server/agents/readiness/audit_engine.py   ← main audit orchestrator
server/agents/readiness/decision_engine.py ← gap_type → action mapper
server/data/audit_prompts.py
server/tools/exa_portfolio_search.py
ui/src/pages/Audit.tsx
ui/src/components/VerdictCard.tsx
```

---

### Phase 2 — The One Thing (Week 5-6)
**Goal**: After the verdict, student gets exactly one concrete action.

**Decision tree** (`decision_engine.py`):
```python
def decide(gap_type: str, gaps: list, audit: ReadinessAudit) -> OneThingAction:
    if gap_type == "ready":
        # generate targeted emails for top 5 matching companies
        return writer_outreach.generate(audit)

    if gap_type == "framing":
        # rewrite specific undefendable bullets
        return reframe_bullets(audit.undefendable_claims, audit.resume_text)

    if gap_type == "skills":
        # pick the highest-frequency gap
        top_gap = max(gaps, key=lambda g: g['jd_frequency'])
        # pull 2-week module from role_projects.json + role_resources.json
        return learning_module_generator.generate(
            role=audit.target_role,
            skill=top_gap['skill'],
            max_weeks=2
        )
```

**For skill gap → learning module**:
- `role_projects.json` has project ideas per role — filter for the specific gap skill
- `role_resources.json` has resources — filter + rank by relevance
- DeepSeek generates a 2-week plan: day 1-3 (learn), day 4-10 (build), day 11-14 (deploy + put on resume)
- Max 1 project. Max 3 resources. No 12-week roadmaps.

**Frontend** (`OneThing.tsx`):
- If "ready to apply": show 5 company cards with generated emails (existing `JobCard.tsx`)
- If "reframe bullets": show side-by-side — original bullet / suggested rewrite
- If "skill gap": show 2-week plan with daily tasks and a "mark done" checkbox
- Deadline counter shown prominently

**Files to create**:
```
server/agents/readiness/one_thing/
  reframe_bullets.py
  learning_module_generator.py   ← wraps existing learning_path.py
ui/src/pages/OneThing.tsx
```

---

### Phase 3 — The Verdict Loop (Week 7-9)
**Goal**: Close the feedback loop. Students log outcomes. System learns.

**Logging** (minimal friction):
- After applying to a job, student logs in one click: ghosted / screen / rejected / offer
- Stored in `application_outcomes` with `audit_id` link

**Pattern detection** (`verdict_loop.py`):
```python
def analyze_patterns(user_id: str) -> VerdictLoopInsight:
    outcomes = get_outcomes(user_id)
    audit = get_latest_audit(user_id)

    # only run if enough data
    if len(outcomes) < 5:
        return VerdictLoopInsight(ready=False, message="Apply to 5+ roles first")

    callback_rate = len([o for o in outcomes if o.outcome != 'ghosted']) / len(outcomes)

    # find similar users in ChromaDB (same role, similar audit profile)
    similar = chromadb.query(audit.embedding, n=20, filter={"gap_type": audit.gap_type})
    peer_callback_rate = mean([s.callback_rate for s in similar if s.callback_rate])

    return VerdictLoopInsight(
        callback_rate=callback_rate,
        peer_callback_rate=peer_callback_rate,
        pattern=identify_pattern(outcomes, audit),
        recommendation=generate_recommendation(callback_rate, peer_callback_rate, audit)
    )
```

**ChromaDB** finally gets used:
- Each audit → embed verdict_text → store with metadata (role, gap_type, percentile)
- Each outcome log → update the stored embedding with outcome data
- Query: "find students with similar audit profile who logged outcomes"
- After 50 users, this becomes the most valuable feature in the product

**Frontend** (`VerdictLoop.tsx`):
- Simple timeline: each job applied → outcome dot (gray/yellow/green)
- One paragraph insight from the pattern detector
- "Your callback rate vs similar profiles" — shown only when n≥10

**Files to create**:
```
server/agents/readiness/verdict_loop.py
server/agents/readiness/cohort_analytics.py
ui/src/pages/VerdictLoop.tsx
ui/src/components/OutcomeTimeline.tsx
```

---

### Phase 4 — Polish + Deploy (Week 10-12)
**Goal**: Production-ready on Vercel + Railway. Real users.

**Security (implement before any real users)**:
```python
# In server/middleware/auth.py
async def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
    return payload["sub"]  # user_id

# In every endpoint that touches a user's data:
@app.post("/audit/start")
async def start_audit(request: AuditRequest, user_id: str = Depends(verify_jwt)):
    # user_id is verified — never trust the request body for this
```

```python
# Resume token: short-lived, signed
def create_resume_token(user_id: str, resume_id: str) -> str:
    return jwt.encode(
        {"user_id": user_id, "resume_id": resume_id, "exp": time() + 900},  # 15 min
        RESUME_TOKEN_SECRET
    )
```

```python
# Input sanitization on city/role
class AuditRequest(BaseModel):
    target_role: constr(max_length=100, pattern=r"^[a-zA-Z0-9 ,.\-/]+$")
    resume_token: Optional[str]
```

**Vercel config** (`vercel.json`):
```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://your-app.railway.app/:path*" }
  ]
}
```

**Railway config** (`railway.toml`):
```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn server.app:app --host 0.0.0.0 --port $PORT --workers 4"
healthcheckPath = "/health"
```

**Dockerfile for Railway**:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## What to Build First (Week 1 Sprint)

Exact order, exact files:

1. `mkdir server/agents/learning server/agents/readiness server/data`
2. Copy Flask `src/*.py` into `server/agents/learning/`, remove Flask imports
3. Copy all JSON data files into `server/data/`
4. Create `server/tools/kimi_client.py`
5. Run existing FastAPI backend — confirm it still starts
6. Write Alembic migration `002_readiness_tables.py`
7. `alembic upgrade head`
8. Deploy to Railway, confirm `/health` returns 200

That's Phase 0 done. Then move to audit_engine.py.

---

## What to Cut If Behind Schedule

Cut in this order — last to cut is always the audit verdict:

1. ChromaDB cohort analytics (Phase 3) — just store outcomes in Postgres, skip similarity search
2. Exa portfolio search — use only Tavily + Perplexity
3. VerdictLoop pattern detection — just show a raw outcome list
4. Learning module generator (Phase 2 skill gap) — just link to role_resources.json filtered results
5. **Never cut**: the audit verdict. That's the product. Everything else is gravy.

---

## The Narrative for Your Portfolio

> I had two separate AI products — a job search engine and a learning path generator.
> Both were solving the wrong layer of the problem. Students weren't failing because
> they couldn't find jobs. They were failing because they couldn't tell if they were
> ready to apply, and had no feedback when they weren't.
>
> I merged both codebases into one backend and built a readiness orchestrator on top —
> a layer that uses live job data as ground truth, Kimi's 1M token context to read
> entire batches of JDs at once, and GPT-4o to write honest verdicts.
>
> The product tells students the truth: ready, not ready, and exactly what changes that.
> Then it tracks what actually happens when they apply. After 50 users, the ChromaDB
> cohort layer starts showing patterns nobody else has data on — because nobody else
> closes the loop.

---

*Last updated: May 2026*
