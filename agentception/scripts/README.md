# Repository scripts

Active scripts have one of three bounded purposes:

- build or validate the canonical synthetic résumé fixtures;
- build offline job-description, skill, match, and embedding evaluation inputs;
- run the repository privacy gate.

No script checks a live key by printing its length/prefix, edits `.env`, keeps a
database awake, embeds a project reference, or applies a production migration.
Provider-backed fixture refreshes run only with explicit intent and keys from the
local environment; generated outputs are reviewed before commit.

Common commands from `agentception/`:

```powershell
uv run --locked python scripts/check_repository_privacy.py
uv run --locked python scripts/build_synthetic_resume_fixture.py --goldens
uv run --locked python scripts/build_synthetic_resume_fixture.py --output tmp/pdfs/synthetic-resume.pdf
```

The generated PDF is temporary and must not be committed.
