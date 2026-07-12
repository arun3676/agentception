# Engineering Roadmap — from working app to AI-engineer portfolio

> **The thesis:** hiring managers in 2026 screen for *production signals* — evals,
> observability, failure handling, cost awareness — not features. Eval literacy is
> described as "the single biggest signal of 'this person actually built with LLMs'"
> ([dev.to hiring survey](https://dev.to/klement_gunndu/5-ai-portfolio-projects-that-actually-get-you-hired-in-2026-5bpl),
> [digitalapplied 2026 skills](https://www.digitalapplied.com/blog/ai-developer-hiring-skills-that-matter-2026)),
> and ~70% of enterprise AI work is observability
> ([letsdatascience portfolio guide](https://letsdatascience.com/blog/the-ml-portfolio-that-actually-gets-you-hired-in-2026)).
> Agentception already *works end-to-end* (119 tests, verified flows). What it lacks
> is the rigor layer. This roadmap adds it, in the order that changes interviews fastest.

**Current verified state (2026-07-11):** resume→profile (Reducto), job search
(Tavily+Exa, real JDs fetched for matching), posted-salary extraction, skill gaps
(taxonomy-filtered), study drawer, interview prep, company intel, applications with
working callback-rate, roadmap visualization, readiness audit endpoints mounted.
119 backend tests green; tsc/lint/build green.

**Known baseline weaknesses (measured, not guessed):**
- Skill vocabulary is a hardcoded ~80-keyword list → 3 of 5 live jobs returned
  **zero** gaps (recall failure), and match scores hit a cosmetic `5.0` floor when
  matching fails.
- Match score is uncalibrated: 43.9 vs 14.3 vs 5.0 with no meaning attached and no
  explanation surfaced.
- No auth; run state in-process; SQLite wiped on redeploy; no rate limiting.
- Zero LLM evals; `.deepeval` folder exists but is referenced by nothing.
- CI runs only `keep-alive.yml` — 119 passing tests are invisible to anyone browsing the repo.
- OpenAI quota exhausted (`429 insufficient_quota` in logs) → silent degradation to
  heuristics; no cost/token tracking anywhere.

---

## Phase 1 — Evaluation harness (the interview-changer)

**Skill you learn/demonstrate:** eval design — golden datasets, extraction P/R/F1,
LLM-as-judge with pinned models, CI gating with tolerance bands. This is the
dividing line interviewers probe first.

**Approach** (per [DeepEval vs RAGAS 2026](https://genai.qa/blog/deepeval-vs-ragas/),
[framework benchmark](https://aiml.qa/llm-evaluation-framework-benchmark-2026/)):
use **DeepEval** — pytest-native, runs in CI like unit tests — as the gate; RAGAS-style
dataset exploration optional later. Best practice: *tolerance bands not exact
thresholds, pinned judge model, stable golden set* so nondeterminism doesn't break CI.

**Build:**
1. `evals/golden/jds/` — 30 real job descriptions (fetch via the existing JD fetcher
   from live ATS URLs; store the text so evals are offline + reproducible).
   Hand-label each with the skills it requires (`evals/golden/jd_skills.jsonl`).
2. `evals/golden/resumes/` — the 14 PDFs in `resume/` + their expected structured
   fields (name/email/experience count/skills) as labels.
3. `evals/test_skill_extraction.py` — precision/recall/F1 of `extract_jd_skills`
   against labels. **Gate: F1 ≥ 0.6 to start; report the number, whatever it is.**
4. `evals/test_resume_parsing.py` — field-level accuracy of Reducto+parser vs labels.
5. `evals/test_match_ranking.py` — for 5 resumes × 30 JDs, hand-label "good/poor fit"
   pairs (~50 pairs); report **AUROC** of the match score. (Research shows
   off-the-shelf matchers score near-random AUROC on hiring —
   [ConFit v2](https://arxiv.org/pdf/2502.12361) — so an honest number here, even a
   mediocre one, is credible and improvable.)
6. `evals/test_study_relevance.py` — DeepEval LLM-judge (pinned model, e.g.
   `deepseek-chat`): "is this resource actually about {topic} at {level}?" over the
   study cache. Gate on relevance ≥ 0.8 with a ±0.05 band.
7. `README` metrics table: extraction F1, parsing accuracy, match AUROC, study
   relevance, plus latency and cost per search (Phase 6 feeds this).

**Acceptance:** `pytest evals/ -m eval` runs offline-deterministic parts in CI on
every push; judge-based evals run nightly. Numbers in README.
**Effort:** 2–3 days (labeling is most of it — label 10 JDs/day).

---

## Phase 2 — CI/CD (cheapest credibility on the board)

**Skill:** GitHub Actions, quality gates, artifact hygiene.

**Build:** `.github/workflows/ci.yml`:
- Job 1 (backend): `pip install -r requirements.txt` → `pytest -q` (119 tests + Phase-1
  deterministic evals).
- Job 2 (frontend): `npm ci && npx tsc --noEmit && npm run lint && npm run build`.
- Job 3 (nightly, `schedule:`): judge-based evals with API keys from repo secrets;
  writes `evals/report.md` artifact.
- README badges: CI status + test count + eval metrics.

**Acceptance:** green badge on README; a PR that breaks extraction F1 by more than
the tolerance band fails CI. **Effort:** half a day.

---

## Phase 3 — Real skill taxonomy (fixes the recall hole)

**Skill:** taxonomy alignment, embedding retrieval over a controlled vocabulary —
the standard pipeline in the literature (extract → candidate-select → match:
[ESCO+EQF linking](https://arxiv.org/pdf/2512.03195),
[ESCOX](https://www.researchgate.net/publication/392571133_ESCOX_A_tool_for_skill_and_occupation_extraction_using_LLMs_from_unstructured_text)).

**Approach:** replace the 80-word list with the **ESCO taxonomy** — free download
(CSV/JSON, all languages, EUPL/Apache licensed,
[download page](https://esco.ec.europa.eu/en/use-esco/download)) — filtered to
digital/tech skills (~1.5–3K concepts):
1. `server/data/skills/esco_tech.json` — one-time transform script in `scripts/`
   (concept id, preferred label, alt labels).
2. `server/tools/skill_extractor.py` — pipeline:
   a. exact/alias match over JD text (fast path, no API);
   b. embedding candidate-selection with Voyage (already wired) for phrases the
      alias pass misses; cache embeddings of the taxonomy once on disk;
   c. optional LLM span-extraction (DeepSeek) only when (a)+(b) find < N skills.
3. Swap `extract_jd_skills` / `analyze_gaps` / skill-gaps router onto it behind a
   flag; **measure Phase-1 F1 before/after** — that before/after delta is your
   interview story.
4. Benchmark option: run against the public
   [ESCO Skill-Extraction benchmark](https://github.com/jensjorisdecorte/Skill-Extraction-benchmark/)
   ([SkillSpan](https://arxiv.org/html/2604.23009) lineage) and cite your score.

**Acceptance:** extraction F1 improves vs Phase-1 baseline; the 3/5-jobs-zero-gaps
case now shows real gaps; taxonomy IDs stored so study topics dedupe ("K8s" = "Kubernetes").
**Effort:** 2–3 days.

---

## Phase 4 — Calibrated, explainable match score

**Skill:** IR ranking (bi-encoder retrieve / cross-encoder rerank —
[ZeroEntropy](https://zeroentropy.dev/articles/biencoder-vs-crossencoder/)),
score calibration, honest UX for model uncertainty.

**Build:**
1. Kill the cosmetic `5.0` floor → return `match_score: null` + `match_status:
   "insufficient_data"`; UI shows "Couldn't assess" instead of a fake number.
2. Score = weighted blend (already hybrid) but **calibrated**: map raw scores to
   labeled good/poor pairs from Phase 1 via isotonic/Platt scaling into meaningful
   bands (Strong ≥70 / Possible 40–70 / Stretch <40). Report AUROC before/after.
3. Explanation payload: `matched_skills`, `missing_skills`, `keyword_score`,
   `semantic_score` → JobCard popover "Why this score".
4. Stretch: cross-encoder rerank of the top 10 (local `bge-reranker` or Voyage
   rerank endpoint) — cite that off-the-shelf rerankers need domain adaptation
   ([ConFit v2](https://arxiv.org/pdf/2502.12361)).

**Acceptance:** no fabricated scores anywhere; every score explains itself; AUROC
reported in README. **Effort:** 1–2 days (+1 for reranker).

---

## Phase 5 — Auth, persistence, security (multi-user honesty)

**Skill:** JWKS/asymmetric JWT verification, RLS-style data scoping, rate limiting.

**Build** (Supabase already in the stack):
1. `server/auth.py` — FastAPI dependency verifying Supabase JWTs via the project
   **JWKS endpoint** (asymmetric ES256/RS256, ~10-min key cache —
   [Supabase JWT docs](https://supabase.com/docs/guides/auth/jwts),
   [FastAPI integration guide](https://dev.to/j0/integrating-fastapi-with-supabase-auth-780)).
   Anonymous mode stays for demo; authenticated requests get real `user_id`.
2. Scope `user_id` on applications, learning paths, resume profiles, outcomes
   (columns exist in sql_store already — populate them).
3. Persistence: move run results + resume profiles from in-process dicts to the
   existing SQLite (dev) / Supabase Postgres (prod); `REDIS_URL` already exists for
   run-state if needed. Survives restart + second instance.
4. `slowapi` rate limits: 10/min on search + LLM endpoints, 60/min default.
5. PII: `DELETE /me/data` purging resume text/profiles/applications; stop logging
   resume characters; document retention in README.

**Acceptance:** restart loses nothing; two browser sessions see separate data;
`curl` hammering search gets 429. **Effort:** 3–4 days.

---

## Phase 6 — LLM routing, cost & observability

**Skill:** the "70% of enterprise AI work" part — cost engineering + tracing.

**Build:**
1. `server/tools/llm_router.py` — single chat-completion entrypoint: DeepSeek
   primary (working key), OpenAI fallback (quota currently exhausted — today's
   silent-degradation bug becomes routing policy), per-call `{provider, model,
   tokens_in/out, cost_usd, latency_ms, purpose}` written to a `llm_calls` table.
2. `/api/v2/system/usage` + a small ops panel on SystemHealth: cost/day, calls by
   provider/purpose, cache hit-rates (search_cache already exists — surface it).
3. Structured logging (one JSON line per request) replacing print-with-emoji on the
   hot paths; keep the emoji for startup only.
4. README gets the cost line every interviewer likes: "a full search costs ~$0.0X".

**Acceptance:** every LLM/search call attributable; dashboards show real numbers;
zero silent fallbacks (all logged + surfaced in health). **Effort:** 2 days.

---

## Phase 7 — Portfolio packaging (the last mile)

**Skill:** technical storytelling — what actually gets the interview.

**Build** (per the portfolio-signal research: story-driven README, architecture
diagram, metrics, demo):
1. README case study: problem → architecture diagram (mermaid) → **metrics table
   from Phase 1/6** (F1, AUROC, relevance, latency, cost) → tradeoffs section
   ("why heuristic + taxonomy instead of fine-tuning", "why DeepSeek-first").
2. Deploy live (Railway + Vercel configs already exist) with the landing page
   linking to the app; demo creds / anonymous mode.
3. 2–3 min Loom: upload resume → matched jobs with salary → gap chip → study drawer
   → roadmap. 4. `docs/EVALS.md`: how the golden set was built, what the numbers
   mean, what you'd do next.

**Acceptance:** a stranger can go from README to live demo to eval numbers in
under 3 minutes. **Effort:** 1–2 days.

---

## Order & why

| # | Phase | Effort | Why this order |
|---|-------|--------|----------------|
| 1 | Evals | 2–3d | Everything after it gets measured against it; biggest hiring signal |
| 2 | CI | 0.5d | Makes 119 tests + evals visible; trivially cheap |
| 3 | ESCO taxonomy | 2–3d | Fixes the real recall hole; before/after F1 is the demo story |
| 4 | Calibrated match | 1–2d | Depends on Phase-1 labels; kills the dishonest 5.0 |
| 5 | Auth/persistence | 3–4d | Biggest lift; product must be multi-user before "live beta" claims |
| 6 | Cost/observability | 2d | Turns today's quota outage into a routing feature |
| 7 | Packaging | 1–2d | Last, so the README numbers are real |

Total ≈ 2–2.5 focused weeks. Phases 1–4 alone change the interview conversation.

## Skills-to-learn map (what to study alongside each phase)

- **Phase 1:** precision/recall/F1 for span extraction; LLM-as-judge pitfalls
  (pin the judge, tolerance bands); DeepEval pytest metrics.
- **Phase 3:** ESCO structure (concepts, alt-labels); embedding nearest-neighbor
  over a vocabulary; when NOT to fine-tune.
- **Phase 4:** bi- vs cross-encoders; AUROC; Platt/isotonic calibration.
- **Phase 5:** JWT/JWKS, asymmetric signing; row-level data scoping; token buckets.
- **Phase 6:** token accounting, cost-per-request math, structured logging/tracing.

## Sources

- [DeepEval vs RAGAS (2026)](https://genai.qa/blog/deepeval-vs-ragas/) · [LLM eval framework benchmark 2026](https://aiml.qa/llm-evaluation-framework-benchmark-2026/) · [deepeval.com comparison](https://deepeval.com/blog/deepeval-vs-ragas)
- [ESCO downloads](https://esco.ec.europa.eu/en/use-esco/download) · [ESCO API/licensing](https://esco.ec.europa.eu/en/use-esco/use-esco-services-api) · [Skill-Extraction benchmark](https://github.com/jensjorisdecorte/Skill-Extraction-benchmark/) · [ESCO+EQF job matching](https://arxiv.org/pdf/2512.03195) · [ESCOX (LLM skill extraction)](https://www.researchgate.net/publication/392571133_ESCOX_A_tool_for_skill_and_occupation_extraction_using_LLMs_from_unstructured_text)
- [Bi- vs cross-encoders](https://zeroentropy.dev/articles/biencoder-vs-crossencoder/) · [ConFit v2 resume-job matching](https://arxiv.org/pdf/2502.12361) · [Explainable job recommendation](https://arxiv.org/pdf/2605.27656)
- [Supabase JWT/JWKS docs](https://supabase.com/docs/guides/auth/jwts) · [FastAPI + Supabase Auth](https://dev.to/j0/integrating-fastapi-with-supabase-auth-780)
- [2026 AI hiring signals](https://dev.to/klement_gunndu/5-ai-portfolio-projects-that-actually-get-you-hired-in-2026-5bpl) · [Skills that matter 2026](https://www.digitalapplied.com/blog/ai-developer-hiring-skills-that-matter-2026) · [ML portfolio guide](https://letsdatascience.com/blog/the-ml-portfolio-that-actually-gets-you-hired-in-2026)
