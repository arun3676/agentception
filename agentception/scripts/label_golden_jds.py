"""Label the golden JDs with the technical skills they actually require.

Labels are produced by an LLM (DeepSeek) with a strict prompt, then written to a
JSONL you can hand-correct — they are the ground truth every extraction metric is
measured against, so they must be reviewed, not trusted blindly. `reviewed: false`
marks rows nobody has checked yet; see docs/EVALS.md.

    python scripts/label_golden_jds.py            # label anything unlabeled
    python scripts/label_golden_jds.py --force    # relabel everything
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

GOLDEN = ROOT / "evals" / "golden"
JDS = GOLDEN / "jds"
INDEX = JDS / "index.jsonl"
LABELS = GOLDEN / "jd_skills.jsonl"

PROMPT = """You are labelling a job description for a skill-extraction benchmark.

List ONLY the concrete technical skills, tools, languages, frameworks, platforms and
technical practices the posting requires or prefers.

Rules:
- Include: programming languages, frameworks, libraries, databases, cloud platforms,
  infrastructure tools, ML/AI techniques, protocols, technical methodologies.
- EXCLUDE: soft skills, company perks, salary, equity, location, employment type,
  seniority words, degrees, years-of-experience, team names, generic verbs.
- Use the canonical common name ("PostgreSQL" not "postgres db"; "Kubernetes" not "k8s").
- One skill per entry, no duplicates, no explanations.

Return ONLY a JSON array of strings. No prose, no markdown fence.

JOB DESCRIPTION:
---
{jd}
---"""


async def label_one(client, model: str, text: str) -> list[str]:
    resp = await asyncio.to_thread(
        client.chat.completions.create,
        model=model,
        messages=[{"role": "user", "content": PROMPT.format(jd=text[:6000])}],
        temperature=0.0,
        max_tokens=600,
    )
    raw = (resp.choices[0].message.content or "").strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        skills = json.loads(raw)
    except json.JSONDecodeError:
        print(f"    ! unparseable label response: {raw[:80]}")
        return []
    return [str(s).strip() for s in skills if isinstance(s, str) and s.strip()][:40]


async def main(force: bool) -> None:
    import openai

    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        sys.exit("DEEPSEEK_API_KEY not set")
    client = openai.OpenAI(api_key=key, base_url="https://api.deepseek.com/v1", timeout=90.0)
    model = "deepseek-chat"

    index = [json.loads(l) for l in INDEX.read_text(encoding="utf-8").splitlines() if l.strip()]

    existing: dict[str, dict] = {}
    if LABELS.exists() and not force:
        for line in LABELS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                existing[rec["id"]] = rec

    todo = [r for r in index if r["id"] not in existing]
    print(f"{len(existing)} labelled, {len(todo)} to label (model={model})")

    for rec in todo:
        text = (JDS / f"{rec['id']}.txt").read_text(encoding="utf-8")
        try:
            skills = await label_one(client, model, text)
        except Exception as e:
            print(f"  x {rec['id']}: {str(e)[:70]}")
            continue
        existing[rec["id"]] = {
            "id": rec["id"],
            "url": rec["url"],
            "title": rec["title"],
            "searched_role": rec["searched_role"],
            "skills": skills,
            "labeled_by": f"llm:{model}",
            "reviewed": False,  # flip to true once a human has checked the row
        }
        print(f"  + {rec['id']} {len(skills):2d} skills  {', '.join(skills[:6])}")

    with LABELS.open("w", encoding="utf-8") as f:
        for rec in existing.values():
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    total = sum(len(r["skills"]) for r in existing.values())
    print(f"\n{len(existing)} JDs labelled, {total} skill mentions -> {LABELS}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.force))
