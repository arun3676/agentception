# Documentation

These are the active documents for the containment release.

| Document | Purpose |
|---|---|
| [Deployment and release safety](DEPLOYMENT.md) | Railway, Vercel, environment boundaries, manual release order, and the Postgres migration gate. |
| [Current job-search flow](job-search-flow-explained.md) | What the anonymous discovery flow actually does today, including failure and durability limits. |
| [Offline evaluations](EVALS.md) | Synthetic fixtures, checked-in metrics, and what those metrics cannot establish. |
| [Privacy history rewrite](PRIVACY_HISTORY_REWRITE.md) | Coordinated post-merge repository-history cleanup and verification. |

The material under [`archive/`](archive/) is superseded planning history. It may
describe deleted routes, obsolete deployment targets, or designs that were never
implemented; do not use it as product or operational documentation.

[`design/COMPETITOR_RESEARCH_2026.md`](design/COMPETITOR_RESEARCH_2026.md) is
date-stamped research input, not evidence that Agentception implements the
features discussed there.
