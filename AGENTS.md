## Agentception Agent Rules

This repo is a safe first target for Telegram-to-PR automation.

When an agent works here:
- Create a feature branch for every requested change.
- Open a pull request instead of pushing directly to `master`.
- Do not deploy automatically.
- Do not add, print, or commit API keys, tokens, resumes, or private user data.
- Keep `.env` files untracked.
- Use `.env.example` for variable names only.
- Run backend import checks and UI build checks before opening a PR when possible.

Expected validation:
- Backend: `python -m compileall server`
- Frontend: `npm --prefix ui run build`

Useful repo context:
- Backend is FastAPI in `server/`.
- Frontend is Next.js in `ui/`.
- Main product flow: discover companies, research them, and generate personalized outreach.
- Current deployment target appears to be Railway.
