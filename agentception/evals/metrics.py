"""Metric helpers shared by the eval suite."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

GOLDEN = Path(__file__).resolve().parent / "golden"
JDS = GOLDEN / "jds"


# --- normalisation -----------------------------------------------------------
# "Node.js", "node js" and "NodeJS" are the same skill. Comparing raw strings
# would understate recall for reasons that have nothing to do with extraction.

_ALIASES = {
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "golang": "go",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "gcp": "googlecloud",
    "googlecloudplatform": "googlecloud",
    "amazonwebservices": "aws",
    "cicd": "cicd",
    "restapis": "rest",
    "restapi": "rest",
    "restfulapis": "rest",
    "nodejs": "node",
    "reactjs": "react",
    "vuejs": "vue",
    "largelanguagemodels": "llm",
    "largelanguagemodel": "llm",
    "llms": "llm",
    "machinelearning": "machinelearning",
    "ml": "machinelearning",
    "retrievalaugmentedgeneration": "rag",
    "naturallanguageprocessing": "nlp",
    "vectordatabases": "vectordatabase",
    "vectordb": "vectordatabase",
}


# Skill names that genuinely end in "s". Stripping the plural off these corrupts
# the token ("kubernetes" -> "kubernete") and splits it from its own alias.
_NEVER_STRIP = {
    "kubernetes", "redis", "pandas", "jenkins", "aws", "devops", "mlops",
    "elasticsearch", "kubeflow", "nats", "numpys", "kibanas",
}


def normalise(skill: str) -> str:
    """Canonical form of a skill name.

    Order matters, and it used to be wrong: plural-stripping ran *before* the alias
    lookup, so "Kubernetes" became "kubernete" and never matched the "k8s" alias,
    and every alias key ending in `s` (nodejs, reactjs, postgres, vuejs, ...) was
    unreachable. Alias -> strip -> alias again.
    """
    s = re.sub(r"[^a-z0-9+#]", "", skill.strip().lower())  # keep c++ / c# distinct
    if not s:
        return ""

    if s in _ALIASES:
        return _ALIASES[s]

    if len(s) > 4 and s.endswith("s") and not s.endswith("ss") and s not in _NEVER_STRIP:
        stripped = s[:-1]
        return _ALIASES.get(stripped, stripped)

    return s


def normalise_all(skills: Iterable[str]) -> set[str]:
    return {n for n in (normalise(s) for s in skills) if n}


# --- classification metrics --------------------------------------------------

@dataclass
class PRF:
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int

    def __str__(self) -> str:
        return (
            f"P={self.precision:.3f} R={self.recall:.3f} F1={self.f1:.3f} "
            f"(tp={self.tp} fp={self.fp} fn={self.fn})"
        )


def prf(predicted: set[str], gold: set[str]) -> PRF:
    tp = len(predicted & gold)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return PRF(precision, recall, f1, tp, fp, fn)


def micro_prf(pairs: list[tuple[set[str], set[str]]]) -> PRF:
    """Micro-average: pool every prediction across documents. Preferred over
    macro here because JDs vary a lot in how many skills they list."""
    tp = sum(len(p & g) for p, g in pairs)
    fp = sum(len(p - g) for p, g in pairs)
    fn = sum(len(g - p) for p, g in pairs)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return PRF(precision, recall, f1, tp, fp, fn)


# --- significance ------------------------------------------------------------

def auroc_permutation_test(
    labels: list[int], scores: list[float], iterations: int = 20000, seed: int = 0
) -> tuple[float, float]:
    """(p_value, null_95th_percentile) for an observed AUROC.

    A small eval set flatters itself. With 6 positives and 8 negatives a *random*
    scorer clears AUROC 0.60 about a quarter of the time, so reporting the number
    alone is close to meaningless. Shuffle the labels, rebuild the null
    distribution, and publish how likely the result was by chance.
    """
    import random

    from sklearn.metrics import roc_auc_score

    observed = roc_auc_score(labels, scores)
    rng = random.Random(seed)
    shuffled = list(labels)

    null = []
    for _ in range(iterations):
        rng.shuffle(shuffled)
        null.append(roc_auc_score(shuffled, scores))

    at_least_as_extreme = sum(1 for v in null if v >= observed)
    p_value = (at_least_as_extreme + 1) / (iterations + 1)

    null.sort()
    p95 = null[int(0.95 * len(null))]
    return p_value, p95


# --- vocabulary ceiling ------------------------------------------------------

def vocabulary_ceiling(gold_sets: list[set[str]], vocabulary: set[str]) -> float:
    """The best recall this extractor could *possibly* achieve.

    A whitelist extractor can only ever return words in its whitelist, so recall is
    capped by how much of the gold vocabulary the whitelist covers. Reporting F1
    without this makes a vocabulary problem look like an extraction problem.
    """
    total = sum(len(g) for g in gold_sets)
    reachable = sum(len(g & vocabulary) for g in gold_sets)
    return reachable / total if total else 0.0


# --- golden set loaders ------------------------------------------------------

def load_jd_labels() -> list[dict]:
    path = GOLDEN / "jd_skills.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_jd_text(jd_id: str) -> str:
    return (JDS / f"{jd_id}.txt").read_text(encoding="utf-8")


def load_match_pairs() -> list[dict]:
    path = GOLDEN / "match_pairs.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_resume_labels() -> list[dict]:
    path = GOLDEN / "resumes.jsonl"
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
