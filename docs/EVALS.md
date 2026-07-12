# Evaluation

Agentception makes three claims that are only worth anything if they're measured:

1. it can tell which **skills a job requires**,
2. it can **rank** jobs against your resume,
3. the **study material** it surfaces is actually about the skill you clicked.

This is how each is measured, what the numbers are, and where they're weak.

```bash
pytest evals/ -m eval      # offline, deterministic, runs in CI
pytest evals/ -m judge     # LLM-as-judge, costs money, nightly
```

Metrics are written to `evals/report.json` and `evals/report.md` on every run.

---

## Baseline results (2026-07-11)

Golden set: **69 real job descriptions**, 1,239 skill labels, 39 match pairs.

| Metric | Value | Reading |
|---|---|---|
| Skill extraction — F1 | **0.535** | ← was 0.405 before the taxonomy swap |
| Skill extraction — precision | **0.728** | |
| Skill extraction — recall | **0.422** | ← was 0.263 |
| Skill extraction — *recall ceiling* | **0.572** | ← was 0.365 |
| Match ranking — AUROC | **0.702** (p=0.017) | ranks in-domain jobs above out-of-domain ones |
| Resume parsing — production (Reducto) | **0.964** | name, email, employer, skills across 14 layouts |
| Resume parsing — fallback (local regex) | **0.714** | known-worse path; published, not hidden |
| Study relevance — LLM judge | **0.950** | the study drawer surfaces on-topic material |

### Skill extraction: a vocabulary problem wearing an extraction problem's clothes

The original extractor scanned for **77 hardcoded keywords**. It looked *precise*
(P=0.890) — but only because it was nearly blind. Only **48 of the 309 distinct
skills** in the golden set were even *in* its list, which capped recall at **0.365**
however good the matching logic was. Measured recall (0.263) was already 72% of
everything reachable, so tuning it was pointless. The vocabulary was the whole problem,
and the `recall_ceiling` metric is what made that visible instead of guessable.

**Phase 3 replaced the vocabulary** (see `server/tools/skill_extractor.py`):

| | keyword list | O*NET taxonomy |
|---|---|---|
| vocabulary | 77 words | **368 skills** (O*NET "Hot Technology" + curated concepts) |
| recall ceiling | 0.365 | **0.572** |
| recall | 0.263 | **0.422** (+60%) |
| precision | 0.890 | 0.728 |
| **F1** | **0.405** | **0.535** (+32%) |

Precision fell on purpose. For a *gap finder*, failing to tell someone about a real
gap is worse than listing one skill they already have — and the floors now enforce the
new operating point, so reverting to the old extractor fails CI on both F1 and recall.

Two things the eval caught while building this, both of which would have shipped:

* **The full 8,155-entry O\*NET catalogue made things worse** (F1 0.377, precision
  0.386). It is a catalogue of *products*, so its long tail — "SoftRisk SQL",
  "Pentagon 2000SQL" — matched constantly. O\*NET's own "Hot Technology" flag is the
  filter; 368 skills beat 8,155.
* **O\*NET spells acronyms out.** It stores SQL as *"Structured query language SQL"*,
  so a posting saying "SQL" matched nothing — SQL was the single biggest false
  negative (22 misses). The builder now indexes the trailing acronym too.

### Reading the AUROC honestly

**0.702 with a permutation p-value of 0.017.** The p-value is reported next to the
number, always, because at small n an AUROC flatters itself: on the *first* version of
this eval (n=14) the score was 0.750 — which sounds better — but p was 0.066 and a
*random* scorer reached 0.771 at the 95th percentile. The prettier number was inside
the noise band. Expanding to n=39 produced a lower score that actually means something.

A metric you can't distinguish from chance is not a metric.

### Two bugs the harness found on its first run

Both were invisible without measurement, which is the argument for building it:

1. **The "hybrid" matcher was silently keyword-only.** `compute_semantic_similarity`
   wrapped the Voyage call in `except: return 0.0`. Voyage rate-limits per minute, a
   search embeds one document per job, so 429s were routine — and each one was
   converted into "these documents are unrelated" rather than "we don't know".
   Fixing it (batch, back off, and return `None` instead of lying) moved
   **AUROC 0.60 → 0.75**.
2. **Truncating JDs to save tokens cost more than it saved.** Capping the embedded
   text at 2.5k chars looked like a free optimisation. Measured, it dropped
   **AUROC 0.75 → 0.60**: an ATS posting opens with company mission and benefits, so
   the first 2.5k chars are mostly the part that *doesn't* carry hiring signal. The
   cap is now 12k.

---

## The golden set

`evals/golden/` — snapshotted so evals are **offline and reproducible**; no network,
no flake, no cost for the deterministic suite.

| File | What |
|---|---|
| `jds/*.txt` + `jds/index.jsonl` | **69 real job descriptions** pulled from live ATS boards (Greenhouse/Lever/Ashby) across 12 role×city queries — AI, ML, LLM, Data, Backend, DevOps, SRE, Frontend, Mobile. Real companies (Anthropic, Chime, Bumble, Mercury, Ripple…). |
| `jd_skills.jsonl` | **1,239 skill labels** — the skills each posting actually requires. |
| `match_pairs.jsonl` | **39** resume↔JD fit pairs (21 positive / 18 negative). |
| `embeddings.json` | Voyage vectors for every eval document, so the *hybrid* matcher runs offline. |
| `resume_parses.json` | Reducto's output for the 14 resume PDFs, so the *production* parser runs offline. |

Rebuild (in order):

```bash
python scripts/build_golden_jds.py --per-role 8   # fetch + snapshot JDs
python scripts/label_golden_jds.py                # label required skills
python scripts/build_match_pairs.py               # build fit pairs
python scripts/build_eval_embeddings.py           # snapshot embeddings
python scripts/build_resume_golden.py             # snapshot Reducto parses
```

### Why paid calls are snapshotted, not mocked

Two of the things worth measuring — the semantic half of the matcher (Voyage) and the
production resume parser (Reducto) — are paid network calls. Mocking them would mean
measuring a fake. Skipping them would mean measuring the *fallback* while reporting it
as the product. So both are executed once, their outputs committed, and replayed
offline. CI runs the real code paths against real model outputs, deterministically,
for free.

Cache keys include the model name and its parameters, so changing the embedder
invalidates the cache instead of silently serving vectors from a model you no longer
ship. A cache miss **raises** — it never degrades to a cheaper path, because a
degraded path would show up as a *model quality* regression rather than the missing
*file* it actually is. (That exact bug produced a phantom AUROC of 0.438 during
development.)

### How the labels were made — and their limits

**Skill labels are LLM-generated (DeepSeek, temperature 0, strict prompt) and are
marked `"reviewed": false` until a human checks the row.** This is the standard
"silver label" tradeoff and it must be stated plainly rather than dressed up:

- *Why it's acceptable:* the labeller (an LLM reading the full JD) and the system
  under test (a keyword list) are completely different mechanisms, so this is not a
  model grading itself. A miss is a real miss.
- *Where it's weak:* the labeller may over-list (tagging a passing mention as a
  requirement), which **depresses recall** and makes our recall number pessimistic.
  It may also normalise differently ("Node.js" vs "NodeJS") — `evals/metrics.py`
  applies an alias/normalisation pass to both sides so this doesn't count as an error.
- *What fixes it:* human review of the 26 rows. Flip `reviewed` to `true` as you go.

**Match labels are weak supervision by role domain.** Every resume in `resume/`
belongs to the same AI/ML engineer, so the answerable question is "does the matcher
rank in-domain postings above out-of-domain ones?" AI Engineer postings are positives,
Frontend/DevOps are negatives, and Backend/Data are **excluded as genuinely ambiguous**
for this profile — a benchmark shouldn't punish a model for a judgement call. It's a
proxy for fit, not fit itself, and it's labelled as such in the file.

---

## Design decisions

**Deterministic vs judged.** Anything measurable with arithmetic (P/R/F1, AUROC,
field accuracy) is deterministic, free, offline, and gates every push. Only study
relevance needs a judge, so only it is `@pytest.mark.judge` and nightly.

**The judge is pinned** (`deepseek-chat`, temperature 0 — `evals/judge_model.py`).
Swapping judge models silently re-scores history. DeepSeek rather than OpenAI because
the OpenAI quota is exhausted in this project and DeepSeek judges far cheaper.

**Gates are floors, not targets** — and tolerance-banded for the judge, so LLM jitter
alone can't fail a build. Raise a floor when the number improves. Never lower one to
make CI green; that is the whole point of having it.

The floors were set by *simulating regressions*, not by guessing. Deleting half the
extractor's vocabulary drops F1 to ~0.24 — so `MIN_F1` is 0.34, above that, and the
gate catches it. The first draft used 0.20, which the half-deleted extractor sailed
straight through: a gate that green-lights a 50% capability loss is decoration.

**Micro-averaged P/R/F1**, not macro: job descriptions vary wildly in how many skills
they list, and macro-averaging would let a 2-skill posting outweigh a 40-skill one.

**A missing golden set fails the build.** Every eval `skipif`s when its inputs are
absent, which is right on a laptop and dangerous in CI — a deleted file would turn the
whole quality gate into a green skip. `test_golden_set_present.py` has no skip.

## Known limitations

Stated because a reviewer will find them anyway, and finding them yourself is the job:

- **Labels are unreviewed LLM output.** All 69 rows are `"reviewed": false`. The
  labeller (DeepSeek reading the full JD) and the system under test (a 77-word keyword
  whitelist) are genuinely independent mechanisms, so this is not a model grading
  itself — but it is silver, not gold. Human review is the next improvement.
- **Resume parsing is one person.** All 14 PDFs are the same candidate in different
  layouts, so it measures *layout robustness*, not generalisation across writers.
  Effective n is the number of templates, not 14. Fixing this needs other people's
  resumes; we won't fabricate them.
- **Match labels are weak supervision.** Fit is derived from the posting's title
  (AI/ML → positive, Frontend/DevOps/SRE/Mobile → negative, ambiguous titles like
  "AI Security Engineer" **dropped**). It's a proxy for fit, not fit itself. An earlier
  version labelled from the *search query* instead of the posting, which put
  "Senior Staff Security Engineer, AI" in the positives and measurably corrupted the
  metric.
- **JD text is truncated at 5,000 chars** by the fetcher and carries some scraped nav
  chrome ("Back to jobs"), so tail-end requirements can be lost.

---

## Roadmap for these numbers

| Phase | Target |
|---|---|
| 3 — ESCO taxonomy | skill-extraction **recall 0.24 → ≥0.60** without giving up precision |
| 4 — calibration | match **AUROC 0.67 → ≥0.75**; remove the fake `5.0` floor |
| 6 — cost tracking | add latency + $/search to this table |
