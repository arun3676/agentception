# Offline evaluations

The deterministic evaluation suite is an engineering regression check. It is not
evidence of hiring probability, applicant quality, ATS performance, or provider
quality in the general population.

Run from `agentception/`:

```powershell
uv run --locked python -m pytest evals -m eval -q --strict-markers
```

The latest checked-in report contains:

| Metric | Value | Scope |
|---|---:|---|
| Skill extraction F1 | 0.5348 | Captured public job-description labels |
| Skill extraction precision | 0.7284 | Same fixture set |
| Skill extraction recall | 0.4225 | Same fixture set |
| Match-ranking AUROC | 0.8095 | Synthetic Jordan Lee profile against 39 weakly supervised pairs |
| AUROC permutation p-value | 0.0004 | Same 39-pair fixture |

These numbers come from `evals/report.json`; tests should not duplicate hard-coded
claims elsewhere.

## Privacy and provenance

- The canonical résumé fixture is a visibly marked synthetic composite identity:
  Jordan Lee, `jordan.lee@example.com`, and the reserved fictional 202-555-0147 number.
- No real résumé PDF is committed. Generate the synthetic PDF temporarily with
  `uv run --locked python scripts/build_synthetic_resume_fixture.py --output tmp/pdfs/synthetic-resume.pdf`.
- Provider-derived parsing and embedding snapshots are tied only to the synthetic
  fixture after the privacy rewrite.
- Captured job descriptions are offline test inputs. Their age and original source
  limit what the evaluation can establish about current listings.

## Limitations

- Match labels are weak supervision based on role domain, not recruiter judgments.
- One synthetic profile cannot demonstrate generalization across candidates,
  careers, writing styles, or résumé layouts.
- Skill labels include model-assisted labels that require human review.
- A cached embedding proves deterministic ranking against that cache; it does not
  prove current Voyage behavior.
- Provider-backed judge tests are non-deterministic and do not gate normal pull requests.

The privacy gate fails when the canonical marker or reserved synthetic identity is
missing, when browser artifacts/databases are tracked, or when banned historical
paths remain after the coordinated rewrite.
