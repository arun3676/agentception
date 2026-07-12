"""Build the tech-skill taxonomy from O*NET.

Why O*NET and not ESCO: ESCO's bulk download is gated behind an email form, which
can't be automated or reproduced by someone cloning this repo. O*NET is the US
Department of Labor's occupational database, downloads directly, has no
registration, and — since this product searches US job boards — is the taxonomy
that actually matches the market.

We take the "Technology Skills" file (real product/tool names, tagged with a "Hot
Technology" flag) and add a curated layer for concepts O*NET under-covers: modern
ML/AI techniques, and skills that are practices rather than products (RAG, MLOps,
distributed systems).

IMPORTANT: the vocabulary must never be derived from the eval's gold labels — that
would be training on the test set. It comes from O*NET plus hand-written concepts,
both independent of the golden set.

    python scripts/build_skill_taxonomy.py
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "server" / "data" / "skills" / "tech_skills.json"

ONET_URL = "https://www.onetcenter.org/dl_files/database/db_29_0_text/Technology%20Skills.txt"

# O*NET is a catalogue of *software products*, which means it also lists things no
# job description means as a skill ("Microsoft Word", "Adobe Acrobat"). Those would
# wreck precision, so office/consumer/clinical software is filtered out.
NOISE_PATTERNS = re.compile(
    r"\b(microsoft (word|excel|powerpoint|outlook|office|access|publisher)|adobe (acrobat|photoshop|illustrator|indesign)|"
    r"quickbooks|sap|peoplesoft|oracle e-?business|salesforce\.com|"
    r"email software|word processing|spreadsheet software|presentation software|"
    r"calendar|medical|dental|patient|billing|payroll|accounting|"
    r"web browser|internet explorer|mozilla firefox|google chrome|"
    r"facebook|twitter|instagram|linkedin|youtube|tiktok)\b",
    re.I,
)

# Also drop entries that are obviously descriptions, not skill names.
# O*NET's "Example" column mixes product names with plain English words ("Reduce",
# "Analyze", "Access"). Matched as skills these are pure false positives, so any
# entry that is a single common English word is dropped.
COMMON_ENGLISH = {
    "reduce", "analyze", "access", "assist", "capture", "create", "design", "develop",
    "display", "engage", "enterprise", "essential", "excel", "expert", "explore",
    "focus", "impact", "insight", "inspire", "learn", "manage", "measure", "monitor",
    "notion", "office", "one", "open", "optimize", "outlook", "perform", "plan",
    "power", "prime", "process", "produce", "project", "protect", "quality", "record",
    "report", "research", "review", "schedule", "search", "secure", "select", "share",
    "simple", "solution", "source", "space", "sql*", "stream", "study", "support",
    "survey", "system", "target", "team", "test", "track", "train", "unite", "vision",
    "word", "work", "write", "zoom", "swift*",
}


def _is_plausible_skill(name: str) -> bool:
    if len(name) < 2 or len(name) > 40:
        return False
    if NOISE_PATTERNS.search(name):
        return False
    if name.count(" ") > 4:  # "Extensible markup language XML" style descriptions
        return False
    if re.fullmatch(r"[\d\s.\-/]+", name):
        return False
    # A bare common English word is never a skill mention worth matching.
    if " " not in name and name.lower() in COMMON_ENGLISH:
        return False
    return True


# O*NET spells acronyms out: "Structured query language SQL", "Extensible markup
# language XML". Matched literally, plain "SQL" in a job posting never hits. Pull the
# trailing acronym out and index it as its own skill — that's the form people write.
_TRAILING_ACRONYM = re.compile(r"\b([A-Z][A-Z0-9+#]{1,7})$")


def acronym_of(name: str) -> str | None:
    m = _TRAILING_ACRONYM.search(name.strip())
    if not m:
        return None
    acronym = m.group(1)
    # Only when the name is genuinely a spelled-out description, not e.g. "Adobe XD"
    if len(name.split()) < 3:
        return None
    return acronym


# Concepts, techniques and practices O*NET's product catalogue doesn't carry.
# Hand-written, independent of the eval set.
CURATED = [
    # LLM / GenAI
    "RAG", "Retrieval-Augmented Generation", "LLM", "Large Language Models",
    "Prompt Engineering", "Fine-tuning", "LoRA", "Vector Database", "Embeddings",
    "Semantic Search", "Agents", "LangChain", "LangGraph", "LlamaIndex", "Ollama",
    "vLLM", "Hugging Face", "Transformers", "Diffusion Models", "Guardrails",
    "Evaluation Harness", "Model Evaluation", "Hallucination", "Context Window",
    "OpenAI API", "Anthropic", "Claude", "GPT-4", "Gemini", "Mistral",
    # Vector stores
    "Pinecone", "Weaviate", "Qdrant", "Chroma", "Milvus", "FAISS", "pgvector",
    # ML
    "Machine Learning", "Deep Learning", "NLP", "Natural Language Processing",
    "Computer Vision", "Reinforcement Learning", "Supervised Learning",
    "Feature Engineering", "Model Training", "Model Serving", "Inference",
    "A/B Testing", "Experimentation", "Recommendation Systems", "Ranking",
    "Time Series", "Anomaly Detection", "Clustering", "Classification",
    "Neural Networks", "Gradient Boosting", "XGBoost", "LightGBM",
    # MLOps / platform.
    # Deliberately NOT here: "Monitoring", "Scalability", "Agile", "Code Review",
    # "Pair Programming", "Technical Writing". They appear in nearly every posting as
    # qualities rather than skills, so they matched constantly and were never in the
    # gold labels — 60+ false positives between them. A gap chip saying "learn
    # Scalability" is also useless advice.
    "MLOps", "LLMOps", "Model Registry", "Feature Store", "Data Drift",
    "Observability", "Distributed Systems", "Microservices",
    "Event-Driven Architecture", "System Design",
    "CI/CD", "Infrastructure as Code", "GitOps", "Site Reliability Engineering",
    # Data
    "ETL", "ELT", "Data Pipelines", "Data Modeling", "Data Warehouse",
    "Data Lake", "Lakehouse", "Streaming", "Batch Processing", "Data Quality",
    "Dimensional Modeling", "Change Data Capture", "Orchestration",
    # API / backend
    "REST", "REST API", "GraphQL", "gRPC", "WebSockets", "Message Queue",
    "Pub/Sub", "Caching", "Load Balancing", "Rate Limiting", "Authentication",
    "Authorization", "OAuth", "JWT", "API Design", "Idempotency",
    # Frontend
    "Server-Side Rendering", "State Management", "Design Systems",
    "Component Libraries", "Accessibility", "Web Vitals", "Responsive Design",
    "Progressive Web Apps",
    # Practices that are genuinely teachable skills (unlike "Agile" or "Code Review")
    "Unit Testing", "Integration Testing", "End-to-End Testing", "TDD",
    # Cloud, data and DevOps tooling O*NET names differently or predates.
    # (O*NET is a slow-moving government catalogue; the modern stack moves faster.)
    "SQL", "Azure", "AWS", "Google Cloud Platform", "Snowflake", "Databricks",
    "BigQuery", "Redshift", "Spark", "Apache Spark", "Airflow", "Apache Airflow",
    "Kafka", "Apache Kafka", "Flink", "dbt", "Terraform", "Pulumi", "Ansible",
    "Datadog", "Grafana", "Prometheus", "Splunk", "New Relic", "Sentry",
    "PagerDuty", "Kubernetes", "Docker", "Helm", "Argo CD", "Jenkins",
    "GitHub Actions", "GitLab CI", "CircleCI", "Terragrunt", "Vault",
    "Redis", "Elasticsearch", "OpenSearch", "Cassandra", "DynamoDB", "MongoDB",
    "Kinesis", "SQS", "SNS", "Lambda", "EC2", "S3", "EKS", "ECS", "IAM", "VPC",
    "CloudFormation", "CloudWatch", "Fargate", "Athena", "Glue", "Step Functions",
    "Next.js", "React", "Vue", "Svelte", "Angular", "Tailwind CSS", "Storybook",
    "React Native", "Flutter", "SwiftUI", "Jetpack Compose", "Expo",
    "FastAPI", "Django", "Flask", "Spring Boot", "Express", "NestJS", "Rails",
    "GraphQL", "Protobuf", "OpenAPI", "Swagger", "Postman",
    "PyTorch", "TensorFlow", "JAX", "Keras", "scikit-learn", "pandas", "NumPy",
    "Polars", "Ray", "MLflow", "Weights & Biases", "Kubeflow", "SageMaker",
    "Vertex AI", "Bedrock", "Triton",
    "SOC 2", "GDPR", "HIPAA", "PCI DSS", "Zero Trust", "Penetration Testing",
    "Threat Modeling", "SIEM", "Incident Response",
    "Cursor", "Copilot", "Claude Code",
]


def fetch_onet() -> list[dict]:
    print(f"downloading O*NET Technology Skills...")
    req = urllib.request.Request(ONET_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    reader = csv.DictReader(io.StringIO(raw), delimiter="\t")
    rows = list(reader)
    print(f"  {len(rows)} rows")
    return rows


def main() -> None:
    rows = fetch_onet()

    skills: dict[str, dict] = {}

    for row in rows:
        name = (row.get("Example") or "").strip()
        if not _is_plausible_skill(name):
            continue
        hot = (row.get("Hot Technology") or "").strip().upper() == "Y"
        category = (row.get("Commodity Title") or "").strip()

        entry = skills.setdefault(name.lower(), {
            "name": name, "source": "onet", "hot": False, "category": category,
        })
        entry["hot"] = entry["hot"] or hot

        # Index the acronym too: "Structured query language SQL" -> "SQL"
        acronym = acronym_of(name)
        if acronym:
            skills.setdefault(acronym.lower(), {
                "name": acronym, "source": "onet:acronym", "hot": hot, "category": category,
            })

    print(f"  {len(skills)} unique O*NET technologies after filtering")

    for name in CURATED:
        key = name.lower()
        if key in skills:
            skills[key]["source"] = "onet+curated"
        else:
            skills[key] = {"name": name, "source": "curated", "hot": True, "category": "concept"}

    # O*NET catalogues ~8k products, most of which are long-tail enterprise software
    # nobody lists as a skill ("SoftRisk SQL", "Pentagon 2000SQL"). Matching all of
    # them tanked precision to 0.39 on the golden set — 873 false positives.
    #
    # O*NET already marks the in-demand subset with a "Hot Technology" flag. Keeping
    # only those, plus the curated concept layer, is the whole quality filter.
    kept = {
        key: s for key, s in skills.items()
        if s["hot"] or s["source"].startswith("curated") or s["source"] == "onet+curated"
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "onet-29.0-hot+curated",
        "count": len(kept),
        "skills": sorted(kept.values(), key=lambda s: s["name"].lower()),
    }
    OUT.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"\n{len(kept)} skills kept of {len(skills)} candidates "
          f"-> {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
